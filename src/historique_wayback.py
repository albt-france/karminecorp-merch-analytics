"""Historique RÉEL du catalogue : pages produit de karminecorp.fr archivées par la Wayback Machine (archive.org).

Pour chaque capture (janvier 2025 -> aujourd'hui) : prix, prix barré, remise et tailles indisponibles.
Sortie : data/raw/wayback/captures.csv (une ligne par capture) et data/raw/wayback/tailles.csv (une ligne par taille).
Les pages téléchargées sont gardées en cache (data/raw/wayback/cache/, non versionné) : relancer ne refait que les manquantes.
Collecte raisonnable : une capture par produit et par mois, 6 requêtes en parallèle au plus, User-Agent explicite.

Limite : archive.org capture les pages au hasard des visites de ses robots ; l'échantillon de produits
varie donc d'un mois à l'autre. Les indicateurs sont des parts (pas des volumes).
"""
from __future__ import annotations

import gzip
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "wayback"
CACHE = OUT / "cache"
UA = {"User-Agent": "kc-case-study/1.0 (etude independante, historique des prix)"}
TAILLES = {"XS", "S", "M", "L", "XL", "XXL", "2XL", "3XL", "XXXL", "4XL"}


def get(url: str, essais: int = 4) -> bytes:
    for i in range(essais):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read()
        except Exception as exc:  # noqa: BLE001
            if i == essais - 1:
                raise
            time.sleep(5 * (i + 1))


def lister_captures() -> pd.DataFrame:
    url = ("http://web.archive.org/cdx/search/cdx?url=karminecorp.fr/products/&matchType=prefix&output=json"
           "&fl=timestamp,original&filter=statuscode:200&from=2025&limit=10000")
    liste = OUT / "cdx.json"
    if not liste.exists():
        liste.write_bytes(get(url))
    rows = json.loads(liste.read_bytes())[1:]
    df = pd.DataFrame(rows, columns=["timestamp", "original"])
    df["handle"] = df.original.str.split("/products/").str[-1].str.split("?").str[0].str.strip("/")
    df = df[(df.handle.str.len() > 0) & ~df.original.str.contains(r"\.(?:oembed|json|js|atom|xml)", regex=True)]
    df["date"] = pd.to_datetime(df.timestamp.str[:8])
    # une capture par produit et par jour
    df["mois"] = df.date.dt.to_period("M")
    # une capture par produit et par mois (la plus récente du mois)
    return df.sort_values("timestamp").drop_duplicates(["handle", "mois"], keep="last").reset_index(drop=True)


def page(ts: str, original: str) -> str:
    f = CACHE / f"{ts}_{re.sub(r'[^a-z0-9-]', '_', original.split('/products/')[-1][:80])}.html.gz"
    if f.exists():
        return gzip.decompress(f.read_bytes()).decode("utf-8", "replace")
    raw = get(f"http://web.archive.org/web/{ts}id_/{original}")
    try:
        raw = gzip.decompress(raw)
    except OSError:
        pass
    f.write_bytes(gzip.compress(raw))
    return raw.decode("utf-8", "replace")


def euros(s: str | None) -> float | None:
    if not s:
        return None
    s = s.replace("€", "").replace(" ", "").replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


S = r'"(?:[^"\\]|\\.)*"'          # une chaîne JSON (avec échappements)
VARIANTE = re.compile(
    r'\{"id":(\d+),"title":' + S + r',"option1":(null|' + S + r'),"option2":(null|' + S + r'),"option3":(null|' + S + r'),'
    r'"sku":(?:null|' + S + r'),"requires_shipping":(?:true|false),"taxable":(?:true|false),"featured_image":.{0,600}?'
    r'"available":(true|false),"name":(' + S + r'),.{0,300}?"price":(\d+),"weight":\d+,"compare_at_price":(null|\d+)')
ANALYTICS = re.compile(r'"name":(' + S + r'),"price":"([\d.]+)","sku":' + S + r',"brand":' + S + r',"variant":(' + S + r'),'
                       r'"category":' + S + r',"nonInteraction":(?:true|false),"remote":(?:true|false),"available":(true|false)')


def _taille(*vals) -> str | None:
    for v in vals:
        if not v or v == "null":
            continue
        for part in v.strip('"').replace("\\/", "/").split("/"):
            t = part.strip().upper().replace("2XL", "XXL").replace("XXXL", "3XL")
            if t in TAILLES:
                return t
    return None


def analyser(html: str) -> dict | None:
    """Prix, prix barré et disponibilité par taille, depuis l'objet produit Shopify de la page."""
    var = {}
    for m in VARIANTE.finditer(html):
        vid, o1, o2, o3, dispo, nom, prix, barre = m.groups()
        var[vid] = dict(taille=_taille(o1, o2, o3), dispo=dispo == "true", prix=int(prix) / 100,
                        barre=int(barre) / 100 if barre != "null" else None, nom=nom.strip("\"").split(" - ")[0])
    if not var:  # thème récent : événements d'analytics (sans prix barré)
        barre_k = re.search(r'CompareAtPrice:\s*"([^"]+)"', html)
        for i, m in enumerate(ANALYTICS.finditer(html)):
            nom, prix, variante, dispo = m.groups()
            var[f"a{i}"] = dict(taille=_taille(variante), dispo=dispo == "true", prix=float(prix),
                                barre=euros(barre_k.group(1)) if barre_k else None, nom=nom.strip("\"").split(" - ")[0])
    if not var:
        return None
    prix = min(v["prix"] for v in var.values())
    barres = [v["barre"] for v in var.values() if v["barre"]]
    tailles = {}
    for v in var.values():
        if v["taille"]:
            tailles[v["taille"]] = tailles.get(v["taille"], False) or v["dispo"]
    titre = next(iter(var.values()))["nom"].strip('"').replace("\\/", "/")
    m = re.search(r"\[([^\]]+)\]", titre)          # pages « une taille par produit » : « Maillot Pro 2026 Rouge [S] »
    if not tailles and m and _taille(m.group(1)):
        tailles[_taille(m.group(1))] = any(v["dispo"] for v in var.values())
    marque = re.search(r'"vendor":"([^"]+)"', html) or re.search(r'"brand":"([^"]+)"', html)
    return {"titre": titre, "marque": marque.group(1) if marque else "", "prix": prix,
            "prix_barre": max(barres) if barres else None, "tailles": tailles,
            "dispo_produit": any(v["dispo"] for v in var.values())}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(exist_ok=True)
    caps = lister_captures()
    limite = int(sys.argv[1]) if len(sys.argv) > 1 else None
    if limite:
        caps = caps.sample(limite, random_state=1)
    print(len(caps), "captures à traiter", flush=True)
    # 6 téléchargements en parallèle au plus (archive.org répond lentement)
    from concurrent.futures import ThreadPoolExecutor

    def charger(r):
        try:
            return analyser(page(r.timestamp, r.original))
        except Exception as exc:  # noqa: BLE001
            print("échec", r.timestamp, r.handle, exc, flush=True)
            return "echec"
    with ThreadPoolExecutor(max_workers=6) as pool:
        resultats = list(pool.map(charger, caps.itertuples()))
    lignes, tailles = [], []
    for i, (r, a) in enumerate(zip(caps.itertuples(), resultats), 1):
        if a == "echec":
            continue
        if i % 50 == 0:
            print(i, "/", len(caps), flush=True)
        if not a or a["prix"] is None:
            continue
        plein = max(a["prix"], a["prix_barre"] or 0)
        remise = round(1 - a["prix"] / plein, 4) if plein else 0
        lignes.append({"date": r.date.date(), "timestamp": r.timestamp, "handle": r.handle, "titre": a["titre"], "marque": a["marque"],
                       "prix_ttc": a["prix"], "prix_plein_ttc": plein, "remise": remise,
                       "disponible": int(a["dispo_produit"]), "nb_tailles": len(a["tailles"]), "nb_tailles_indisponibles": sum(not v for v in a["tailles"].values())})
        for t, dispo in a["tailles"].items():
            tailles.append({"date": r.date.date(), "timestamp": r.timestamp, "handle": r.handle, "taille": t, "disponible": int(dispo)})
    pd.DataFrame(lignes).to_csv(OUT / "captures.csv", index=False)
    pd.DataFrame(tailles).to_csv(OUT / "tailles.csv", index=False)
    print("captures exploitables :", len(lignes), "| lignes taille :", len(tailles))


if __name__ == "__main__":
    main()
