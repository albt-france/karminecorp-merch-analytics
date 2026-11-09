"""Relevé quotidien du catalogue public de la boutique Karmine Corp.

Lit l'endpoint public Shopify /products.json (prix, remises, disponibilité par variante)
et enregistre :
  - le JSON brut du jour : data/raw/boutique/products_AAAA-MM-JJ.json
  - une ligne par variante dans : data/raw/boutique/variants_snapshots.csv

Le script n'utilise que la bibliothèque standard (pour tourner dans une tâche planifiée).
Il ne fait rien si le relevé du jour existe déjà (sauf avec --force) ou après la date de fin.
Limite : Shopify n'expose pas les quantités en stock, seulement « disponible ou non ».
"""
from __future__ import annotations

import csv
import json
import re
import sys
import time
import urllib.request
from datetime import date, datetime
from pathlib import Path


BASE_URL = "https://www.karminecorp.fr/products.json"
USER_AGENT = "kc-case-study/1.0 (etude independante, releve quotidien)"
END_DATE = date(2026, 12, 1)  # après le Black Friday (27/11) et le Cyber Monday (30/11)
# Heure locale du PC (Paris). Windows n'a pas la base tzdata.

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "raw" / "boutique"
CSV_PATH = OUT_DIR / "variants_snapshots.csv"
LOG_PATH = ROOT / "logs" / "snapshot_boutique.log"

SIZE_RE = re.compile(r"^(XXS|XS|S|M|L|XL|XXL|2XL|XXXL|3XL|4XL)$", re.IGNORECASE)
SIZE_NORMALISE = {"2XL": "XXL", "XXXL": "3XL"}

FIELDS = [
    "snapshot_date", "snapshot_ts", "product_id", "handle", "title", "product_type",
    "vendor", "tags", "published_at", "created_at", "updated_at", "is_preorder",
    "variant_id", "variant_title", "sku", "option1", "option2", "option3", "size",
    "price", "compare_at_price", "discount_pct", "available",
]


def log(msg: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.now().astimezone().isoformat(timespec='seconds')} {msg}"
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line)


def fetch_page(page: int, retries: int = 3) -> list[dict]:
    url = f"{BASE_URL}?limit=250&page={page}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))["products"]
        except Exception as exc:  # réseau, 429, etc.
            log(f"page {page} essai {attempt} échec : {exc!r}")
            time.sleep(10 * attempt)
    raise RuntimeError(f"Impossible de lire la page {page}")


def fetch_all() -> list[dict]:
    products: list[dict] = []
    for page in range(1, 21):
        batch = fetch_page(page)
        if not batch:
            break
        products.extend(batch)
        time.sleep(1.5)  # rester poli avec le serveur
    return products


def parse_size(variant: dict) -> str:
    for key in ("option1", "option2", "option3"):
        val = (variant.get(key) or "").strip()
        if SIZE_RE.match(val):
            val = val.upper()
            return SIZE_NORMALISE.get(val, val)
    return ""


def to_rows(products: list[dict], snap_date: str, snap_ts: str) -> list[dict]:
    rows = []
    for p in products:
        preorder = "précommande" in p["title"].lower() or "precommande" in p["title"].lower()
        for v in p["variants"]:
            price = float(v["price"])
            cmp = float(v["compare_at_price"]) if v.get("compare_at_price") else None
            discount = round(1 - price / cmp, 4) if cmp and cmp > price else 0.0
            rows.append({
                "snapshot_date": snap_date,
                "snapshot_ts": snap_ts,
                "product_id": p["id"],
                "handle": p["handle"],
                "title": p["title"],
                "product_type": p.get("product_type", ""),
                "vendor": p.get("vendor", ""),
                "tags": "|".join(p.get("tags", [])) if isinstance(p.get("tags"), list) else p.get("tags", ""),
                "published_at": p.get("published_at", ""),
                "created_at": p.get("created_at", ""),
                "updated_at": p.get("updated_at", ""),
                "is_preorder": int(preorder),
                "variant_id": v["id"],
                "variant_title": v.get("title", ""),
                "sku": v.get("sku", ""),
                "option1": v.get("option1") or "",
                "option2": v.get("option2") or "",
                "option3": v.get("option3") or "",
                "size": parse_size(v),
                "price": price,
                "compare_at_price": cmp if cmp is not None else "",
                "discount_pct": discount,
                "available": int(bool(v.get("available"))),
            })
    return rows


def main() -> int:
    force = "--force" in sys.argv
    now = datetime.now().astimezone()
    today = now.date()
    if today > END_DATE and not force:
        log(f"date de fin dépassée ({END_DATE}), rien à faire")
        return 0
    json_path = OUT_DIR / f"products_{today.isoformat()}.json"
    if json_path.exists() and not force:
        log(f"relevé du {today} déjà présent, rien à faire")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    products = fetch_all()
    json_path.write_text(json.dumps(products, ensure_ascii=False), encoding="utf-8")

    rows = to_rows(products, today.isoformat(), now.isoformat(timespec="seconds"))
    new_file = not CSV_PATH.exists()
    if force and not new_file:  # retirer les lignes déjà écrites pour ce jour
        with CSV_PATH.open(encoding="utf-8", newline="") as f:
            kept = [r for r in csv.DictReader(f) if r["snapshot_date"] != today.isoformat()]
        with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(kept)
    with CSV_PATH.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            w.writeheader()
        w.writerows(rows)

    n_disc = sum(1 for p in products if any(
        v.get("compare_at_price") and float(v["compare_at_price"]) > float(v["price"]) for v in p["variants"]))
    n_out = sum(1 for r in rows if not r["available"])
    log(f"OK {today} : {len(products)} produits, {len(rows)} variantes, "
        f"{n_disc} produits remisés, {n_out} variantes épuisées")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        log(f"ERREUR : {exc!r}")
        sys.exit(1)
