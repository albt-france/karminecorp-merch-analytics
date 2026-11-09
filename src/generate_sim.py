"""Données SIMULÉES pour l'étude de cas « La data derrière la Blue Wall ».

Ce ne sont PAS des données de la Karmine Corp. Elles servent à démontrer les méthodes
(prévision d'un drop, courbe de tailles, démarques, RFM, LTV, billetterie, test A/B).

Ce qui est calé sur du RÉEL :
  - le catalogue (produits, prix pleins, remises, tailles, disponibilité au 09/11/2026),
    lu dans data/raw/boutique/products_2026-11-09.json ;
  - le calendrier sportif 2025-2026 (data/clean/kc_resultats_lol.csv) qui crée les pics de ventes ;
  - les ordres de grandeur publiés : merch ≈ 2,5 M€ HT en 2023 et objectif ≈ 4 M€ en 2024
    (Sheep Esports), livraison offerte dès 120 €, capacité des Arènes (3 000 places).

Tout le reste est une HYPOTHÈSE écrite dans les constantes ci-dessous.
Graine fixe : relancer le script redonne exactement les mêmes fichiers.

Sorties (data/clean/sim_*.csv) :
  sim_produits, sim_variantes, sim_clients, sim_commandes, sim_lignes, sim_stock,
  sim_alertes_stock, sim_remises_jour, sim_evenements, sim_billets, sim_liste_attente,
  sim_ab_test
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 2026
ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / "data" / "raw" / "boutique" / "products_2026-11-09.json"
RESULTATS = ROOT / "data" / "clean" / "kc_resultats_lol.csv"
OUT = ROOT / "data" / "clean"

START, END = pd.Timestamp("2025-01-01"), pd.Timestamp("2026-11-08")
DAYS = pd.date_range(START, END, freq="D")
T = len(DAYS)
TVA = 1.20

# --- Hypothèses de calage -------------------------------------------------------------
TARGET_CA_HT_2025 = 4_000_000          # merch 2025, HT, hors frais de port (ordre de grandeur publié)
SEUIL_LIVRAISON_OFFERTE = 120.0        # réel (bandeau de la boutique)
FRAIS_PORT = 6.90                      # hypothèse
N_CLIENTS_AVANT_2025 = 45_000          # clients ayant acheté avant la période simulée (hypothèse)

# Courbe de tailles de la DEMANDE (hypothèse, profil textile homme 16-35 ans)
TAILLES = ["XS", "S", "M", "L", "XL", "XXL", "3XL", "4XL"]
PART_TAILLE = {"XS": .03, "S": .11, "M": .23, "L": .26, "XL": .19, "XXL": .11, "3XL": .06, "4XL": .01}

# Fenêtres de prix (hypothèses ; le BF 2026 est en cours au moment du relevé réel)
# Calé sur l'historique RÉEL archivé (archive.org) : aucune remise en 2025, des soldes en mars-avril 2026
# (73 % puis 64 % des pages soldées, remise médiane ~40 %), puis le Black Friday 2026 (relevé du 09/11/2026).
SOLDES = [("2026-03-01", "2026-04-30")]
BF_2026 = ("2026-11-02", str(END.date()))

# Coût de revient en part du prix plein HT (hypothèses)
TAUX_COUT = {"maillot": .35, "textile": .38, "accessoire": .30, "cartes": .50,
             "peluche": .40, "deco": .45, "service": .20}

# Demande annuelle « de base » à prix plein, en unités, par type (avant facteur d'échelle global)
BASE_TYPE = {"Maillot": 2500, "Veste": 900, "Jogging": 700, "Pantalon": 350, "Hoodie": 700,
             "Crewneck": 500, "T-shirt": 900, "Chemise": 250, "Short": 300, "Brassière": 150,
             "Casquette": 600, "Manchette": 500, "Drapeau": 700, "Chaussette": 400,
             "Peluche": 1300, "Carte": 900, "TCG": 1500, "Néon": 30, "Accessoire": 1500,
             "Service": 0}
MULT_COLLECTION = {"Héritage 2023-2024": .35, "Pro Kit 2025": 1.5, "Pro Kit 2026": 1.5,
                   "Worlds 2026": 1.5, "Pro Kit Worlds 2025": .9, "Collab Blue Lock": 1.0,
                   "Campus": .8, "Eclipse": .7, "FW25": .8, "Été 2025": .6, "Basket": .5,
                   "Signature FW26": .8, "Eternal 2026": 1.0, "Loup": 1.0, "Cartes et TCG": 1.0,
                   "Accessoires": 1.0}
PRODUITS_PHARES = {  # remplace le multiplicateur de collection
    r"^Maillot Pro 2025$": 6.0, r"^Maillot Pro 2026 Bleu$": 3.4, r"^Maillot Pro 2026 Rouge$": 2.6,
    r"^Maillot Worlds 2026": 3.0, r"^Maillot Pro Eternal 2026$": 1.6,
    r"^ROAD TO WORLDS 2026": 2.0, r"^Booster": 3.0, r"^Pack de 5 Boosters": 1.0,
    r"^Display": .15, r"^Classeur": .5, r"^Playmat": .5, r"^Artbook": .6, r"^Pack Canna": .05,
}
# Courbe de tailles COMMANDÉE par rapport à la demande (hypothèse) : on commande une courbe
# « standard » trop centrée, donc trop de XS et pas assez de XXL / 3XL.
BIAIS_COMMANDE_TAILLE = {"XS": 1.6, "S": 1.05, "M": 1.0, "L": 1.0, "XL": .95, "XXL": .82,
                         "3XL": .72, "4XL": 1.0, "TU": 1.0}
HYPE_BF = (2.5, 1.3)   # multiplicateur de demande pendant le Black Friday (produit remisé, prix plein)
ELASTICITE = 1.2       # demande × (1 - remise)^-1.2, plafonnée à × 4
SENSIBILITE_MATCH = {"maillot": 1.0, "accessoire": .7, "cartes": .6, "textile": .4,
                     "peluche": .3, "deco": .2, "service": 1.0}

COLLECTIONS = [  # l'ordre compte
    (r"Worlds 2026|ROAD TO WORLDS", "Worlds 2026"),
    (r"Worlds 2025", "Pro Kit Worlds 2025"),
    (r"Pro 2026|Pro Kit 2026", "Pro Kit 2026"),
    (r"Pro 2025|Pro Kit 2025", "Pro Kit 2025"),
    (r"Eternal", "Eternal 2026"),
    (r"Blue Lock", "Collab Blue Lock"),
    (r"Basket", "Basket"),
    (r"Campus|Crewneck Knit", "Campus"),
    (r"Eclipse", "Eclipse"),
    (r"FW25", "FW25"),
    (r"Denim|Chemise light blue|T-Shirt Blanc|Chaussettes", "Été 2025"),
    (r"Signature|Metal|Butterfly|Essentials", "Signature FW26"),
    (r"Loup", "Loup"),
    (r"collector|Booster|Display|Classeur|Playmat|Artbook", "Cartes et TCG"),
    (r"KCX 3|L.gende|Monogram|Ultra|University|Classique|Pro Kit +2023|Pro Kit 2024", "Héritage 2023-2024"),
]

rng = np.random.default_rng(SEED)


def window_mask(a: str, b: str) -> np.ndarray:
    return np.asarray((DAYS >= pd.Timestamp(a)) & (DAYS <= pd.Timestamp(b)))


# ======================================================================================
# 1. Produits et variantes (calés sur le catalogue réel)
# ======================================================================================
def normalise_type(title: str, ptype: str) -> str:
    t = title.lower()
    if re.search(r"booster|display|classeur|playmat|artbook", t):
        return "TCG"
    if "carte collector" in t:
        return "Carte"
    if "personnalisation" in t:
        return "Service"
    mapping = {"jogging": "Jogging", "néon": "Néon", "carte": "Carte", "Brassière": "Brassière"}
    if ptype:
        return mapping.get(ptype, ptype)
    if re.search(r"pin's|porte cl|tote bag|pack canna", t):
        return "Accessoire"
    return "Accessoire"


def famille(ptype: str) -> str:
    if ptype == "Maillot":
        return "maillot"
    if ptype in ("Carte", "TCG"):
        return "cartes"
    if ptype == "Peluche":
        return "peluche"
    if ptype == "Néon":
        return "deco"
    if ptype == "Service":
        return "service"
    if ptype in ("Casquette", "Manchette", "Drapeau", "Chaussette", "Accessoire"):
        return "accessoire"
    return "textile"


def collection(title: str) -> str:
    for pat, name in COLLECTIONS:
        if re.search(pat, title, flags=re.IGNORECASE):
            return name
    return "Accessoires"


def date_lancement(created: pd.Timestamp, published: pd.Timestamp, coll: str) -> tuple[pd.Timestamp, str]:
    """Hypothèse : la date de publication Shopify si elle est proche de la création ;
    sinon le produit a été republié, et on prend création + 21 jours."""
    if coll == "Pro Kit 2026":
        return pd.Timestamp("2025-12-10"), "hypothèse : avant le début du LEC Versus 2026"
    if (published - created).days <= 60:
        return published.normalize(), "date de publication Shopify"
    return (created + pd.Timedelta(days=21)).normalize(), "création Shopify + 21 jours (produit republié)"


def charger_produits() -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    prods, vars_ = [], []
    for p in raw:
        title = p["title"].strip()
        if "carte cadeau" in title.lower():
            continue
        ptype = normalise_type(title, p.get("product_type") or "")
        coll = collection(title)
        created = pd.Timestamp(p["created_at"]).tz_localize(None)
        published = pd.Timestamp(p["published_at"]).tz_localize(None)
        launch, regle = date_lancement(created, published, coll)
        prices = [float(v["price"]) for v in p["variants"]]
        cmps = [float(v["compare_at_price"]) if v.get("compare_at_price") else 0.0 for v in p["variants"]]
        full = max(max(prices), max(cmps))
        remise = float(np.median([1 - pr / full for pr in prices]))
        tl = title.lower()
        preco = "précommande" in tl or "expéditions à partir" in tl
        if "mi-janvier" in tl:
            expedition = "2027-01-15"
        elif "14 octobre" in tl:
            expedition = "2026-10-14"
        elif "10 à 12 semaines" in tl:
            expedition = "commande + 77 jours"
        else:
            expedition = ""
        nom = re.split(r" - (Pr.commande|Exp.ditions)", title)[0].strip()
        prods.append(dict(product_id=str(p["id"]), nom=nom, titre_catalogue=title, type=ptype,
                          famille=famille(ptype), collection=coll, date_creation=created.normalize(),
                          date_lancement=launch, regle_date_lancement=regle,
                          prix_plein_ttc=round(full, 2), remise_reelle_20261109=round(remise, 4),
                          precommande=int(preco), expedition_prevue=expedition,
                          origine="catalogue réel"))
        for v in p["variants"]:
            size = ""
            for k in ("option1", "option2", "option3"):
                val = (v.get(k) or "").strip().upper().replace("2XL", "XXL").replace("XXXL", "3XL")
                if val in PART_TAILLE:
                    size = val
                    break
            vars_.append(dict(variant_id=str(v["id"]), product_id=str(p["id"]), taille=size or "TU",
                              dispo_reelle_20261109=int(bool(v.get("available")))))

    # Maillots de saison retirés du catalogue public (pages en 404) : prix et dates en HYPOTHÈSE
    for pid, nom, prix, launch, remise in [("R-1", "Maillot Pro 2025", 75.0, "2025-01-10", 0.30),
                                           ("R-2", "Maillot Pro 2026 Bleu", 80.0, "2025-12-10", 0.10)]:
        prods.append(dict(product_id=pid, nom=nom, titre_catalogue=nom, type="Maillot", famille="maillot",
                          collection=collection(nom), date_creation=pd.Timestamp(launch),
                          date_lancement=pd.Timestamp(launch),
                          regle_date_lancement="hypothèse (produit retiré du catalogue public)",
                          prix_plein_ttc=prix, remise_reelle_20261109=remise, precommande=0,
                          expedition_prevue="", origine="reconstitué (hypothèse)"))
        for s in TAILLES[:7]:
            vars_.append(dict(variant_id=f"{pid}-{s}", product_id=pid, taille=s, dispo_reelle_20261109=0))

    produits = pd.DataFrame(prods)
    variantes = pd.DataFrame(vars_)
    # une seule ligne par taille et par produit (certains produits ont plusieurs options, ex. couleur)
    variantes = variantes.drop_duplicates(["product_id", "taille"]).reset_index(drop=True)
    produits["cout_unitaire_ht"] = (produits.prix_plein_ttc / TVA * produits.famille.map(TAUX_COUT)).round(2)
    return produits, variantes


# ======================================================================================
# 2. Demande attendue (λ) par variante et par jour
# ======================================================================================
def intensite_evenements() -> np.ndarray:
    """Effet des moments sportifs RÉELS (calendrier 2025-2026), décroissant sur quelques jours."""
    res = pd.read_csv(RESULTATS, parse_dates=["date"])
    E = np.zeros(T)
    for r in res.itertuples():
        if r.phase.startswith("Fin de saison"):
            continue
        i = 0.12 + (0.12 if r.resultat == "V" else 0)
        enjeu = str(r.enjeu) if isinstance(r.enjeu, str) else ""
        if "Qualifiée" in enjeu:
            i += 0.45
        if r.phase == "Finale":
            i += 0.5
        if "Championne" in enjeu:
            i += 1.0
        if r.competition == "EWC" and r.phase == "Finale":
            i += 0.4          # finale à domicile, à Paris
        if r.competition == "Worlds" and r.phase == "Quart de finale":
            i += 0.6
        t0 = (r.date - START).days
        for lag in range(-3, 11):
            t = t0 + lag
            if 0 <= t < T:
                if lag >= 0:
                    E[t] += i * np.exp(-lag / 2.5)
                elif r.phase == "Finale":
                    E[t] += 0.25 * i * np.exp(lag / 1.5)   # anticipation avant une finale
    return E


def saison() -> np.ndarray:
    mois = {1: 1.10, 2: 1.0, 3: 1.0, 4: .92, 5: .92, 6: .88, 7: .85, 8: .82, 9: 1.0, 10: 1.05, 11: 1.15, 12: 1.0}
    s = np.array([mois[d.month] for d in DAYS])
    s *= np.where(DAYS.day_of_week >= 5, 1.12, 0.95)                       # week-ends (jours de match)
    noel = (DAYS.month == 12) & (DAYS.day <= 20)
    s *= np.where(noel, 1.5, 1.0)
    s *= np.where((DAYS.month == 12) & (DAYS.day > 20), 0.7, 1.0)
    return s


def chemin_remise(launch: pd.Timestamp, d_final: float, fin: pd.Timestamp | None) -> np.ndarray:
    """Remise appliquée chaque jour. Elle finit au niveau RÉEL relevé le 09/11/2026 (BF 2026)."""
    d = np.zeros(T)
    if d_final <= 0:
        return d
    age = np.asarray((DAYS - launch).days)
    lvl_soldes = min(d_final, .40)
    for a, b in SOLDES:
        m = window_mask(a, b) & (age >= 60)
        d = np.where(m, np.maximum(d, lvl_soldes), d)
    if fin is None:                           # produit encore en ligne : niveau réel du BF 2026
        d = np.where(window_mask(*BF_2026), d_final, d)
    return np.round(d, 4)


def construire_lambda(produits: pd.DataFrame, variantes: pd.DataFrame, E: np.ndarray) -> tuple:
    S = saison()
    bf = window_mask(*BF_2026)
    lam_prod, remises = {}, {}
    for p in produits.itertuples():
        base = BASE_TYPE.get(p.type, 600)
        mult = MULT_COLLECTION.get(p.collection, 1.0)
        for pat, m in PRODUITS_PHARES.items():
            if re.search(pat, p.nom):
                mult = m
        tau = {"maillot": 220, "accessoire": 200, "cartes": 150, "peluche": 150}.get(p.famille, 100)
        pic = {"maillot": .12, "accessoire": .05}.get(p.famille, .15)
        age = np.asarray((DAYS - p.date_lancement).days, dtype=float)
        a = np.clip(age, 0, None)
        g = pic / 3 * np.exp(-a / 3) + (1 - pic) / tau * np.exp(-a / tau) + 0.10 / 365   # + fond « permanent »
        g = np.where(age >= 0, g, 0.0)
        fin = pd.Timestamp("2026-02-28") if p.nom == "Maillot Pro 2025" else None       # retiré après la saison
        if fin is not None:
            g = np.where(DAYS <= fin, g, 0.0)
        d = chemin_remise(p.date_lancement, p.remise_reelle_20261109, fin)
        elas = np.minimum((1 - d) ** (-ELASTICITE), 4.0)
        hype_bf = np.where(bf & (d > 0), HYPE_BF[0], np.where(bf, HYPE_BF[1], 1.0))
        lam = base * mult * g * S * (1 + SENSIBILITE_MATCH[p.famille] * E) * elas * hype_bf
        lam_prod[p.product_id] = lam
        remises[p.product_id] = d
    # répartition par taille
    lam_var = np.zeros((len(variantes), T))
    for pid, grp in variantes.groupby("product_id"):
        parts = np.array([PART_TAILLE.get(s, 1.0) for s in grp.taille])
        parts = parts / parts.sum()
        lam_var[grp.index.values] = parts[:, None] * lam_prod[pid][None, :]
    return lam_var, remises


# ======================================================================================
# 3. Stock, ventes et ruptures
# ======================================================================================
def quantites_initiales(produits, variantes, lam_var) -> np.ndarray:
    """Hypothèse clé : la production est calée sur la demande attendue, et sur l'état RÉEL
    de la boutique le 09/11/2026 : une taille épuisée a été sous-produite ; un produit très
    remisé a été sur-produit (plus la remise réelle est forte, plus le surstock est grand)."""
    p = produits.set_index("product_id")
    cum = lam_var.sum(axis=1)
    d_final = variantes.product_id.map(p.remise_reelle_20261109).values
    preco = variantes.product_id.map(p.precommande).values.astype(bool)
    dispo = variantes.dispo_reelle_20261109.values.astype(bool)
    biais = variantes.taille.map(BIAIS_COMMANDE_TAILLE).values
    f_dispo = 1.05 + 1.3 * d_final + rng.normal(0, .12, len(variantes)).clip(-.2, .4)
    f_dispo = np.maximum(f_dispo * biais, 1.02)          # reste disponible au 09/11/2026, comme en vrai
    f_epuise = rng.uniform(.70, .92, len(variantes)) * np.minimum(biais, 1.0)
    q = np.where(dispo, cum * f_dispo, cum * f_epuise)
    q = np.round(q).astype(float)
    q[preco & dispo] = np.inf                  # fabriqué à la commande pendant la précommande
    return q


def simuler_ventes(lam_var: np.ndarray, q0: np.ndarray):
    stock = q0.copy()
    ventes = np.zeros_like(lam_var, dtype=np.int32)
    perdues = np.zeros_like(lam_var, dtype=np.int32)
    date_rupture = np.full(len(q0), -1)
    for t in range(T):
        dem = rng.poisson(lam_var[:, t])
        sold = np.minimum(dem, stock)
        stock = stock - sold
        ventes[:, t] = sold
        perdues[:, t] = dem - sold
        newly = (stock <= 0) & (date_rupture < 0) & (sold > 0)
        date_rupture[newly] = t
    return ventes, perdues, stock, date_rupture


# ======================================================================================
# 4. Commandes et clients
# ======================================================================================
PAYS = {"FR": .80, "BE": .06, "CH": .04, "CA": .02, "ES": .02, "LU": .01, "DE": .015, "Autres": .035}
SOURCES_NOUVEAU = {"direct": .22, "instagram": .20, "tiktok": .15, "twitch": .15, "x": .08,
                   "google": .12, "newsletter": .03, "autre": .05}
SOURCES_RETOUR = {"direct": .30, "instagram": .12, "tiktok": .07, "twitch": .12, "x": .06,
                  "google": .05, "newsletter": .25, "autre": .03}
TAILLE_PANIER = ([1, 2, 3, 4], [.62, .26, .09, .03])


def tirer_source(retour: bool, e: float) -> str:
    base = SOURCES_RETOUR if retour else SOURCES_NOUVEAU
    keys = list(base)
    p = np.array([base[k] for k in keys])
    p[keys.index("twitch")] *= 1 + 1.5 * e     # les soirs de match, Twitch pèse plus
    return keys[rng.choice(len(keys), p=p / p.sum())]


def construire_commandes(produits, variantes, ventes, remises, E):
    p = produits.set_index("product_id")
    v_pid = variantes.product_id.values
    v_size = variantes.taille.values
    prix = variantes.product_id.map(p.prix_plein_ttc).values
    is_jersey = variantes.product_id.map(p.famille).values == "maillot"
    perso_pid = p.index[p.type == "Service"]
    perso_pid = perso_pid[0] if len(perso_pid) else None
    perso_vid = variantes.loc[variantes.product_id == perso_pid, "variant_id"].iloc[0] if perso_pid else None
    perso_prix = p.loc[perso_pid, "prix_plein_ttc"] if perso_pid else 0

    # clients avant 2025 (pas de commandes dans les données, mais ils peuvent racheter)
    max_c = 400_000
    c_size = np.empty(max_c, dtype=object)
    c_loyal = np.zeros(max_c)
    c_last = np.zeros(max_c, dtype=int)
    c_first = np.zeros(max_c, dtype=int)
    c_pays = np.empty(max_c, dtype=object)
    c_src = np.empty(max_c, dtype=object)
    n0 = N_CLIENTS_AVANT_2025
    c_size[:n0] = rng.choice(TAILLES, n0, p=list(PART_TAILLE.values()))
    c_loyal[:n0] = rng.lognormal(0, 1.0, n0)
    c_first[:n0] = -rng.integers(60, 1500, n0)
    c_last[:n0] = c_first[:n0] + (rng.random(n0) * -c_first[:n0] * .9).astype(int)
    c_pays[:n0] = rng.choice(list(PAYS), n0, p=list(PAYS.values()))
    c_src[:n0] = "avant 2025"
    n_c = n0

    # part de clients qui reviennent : plus forte les jours de lancement
    launch_days = set((produits.date_lancement - START).dt.days.tolist())
    orders, lines = [], []
    oid = 0
    for t in range(T):
        sold_idx = np.nonzero(ventes[:, t])[0]
        if len(sold_idx) == 0:
            continue
        units = np.repeat(sold_idx, ventes[sold_idx, t])
        rng.shuffle(units)
        sized = units[v_size[units] != "TU"]
        tu = units[v_size[units] == "TU"]
        paniers = []                         # (taille, [variant_idx...])
        for s in TAILLES:
            u = sized[v_size[sized] == s]
            i = 0
            while i < len(u):
                k = rng.choice(TAILLE_PANIER[0], p=TAILLE_PANIER[1])
                paniers.append([s, list(u[i:i + k])])
                i += k
        for u in tu:
            if paniers and rng.random() < .45:
                paniers[rng.integers(len(paniers))][1].append(u)
            else:
                paniers.append(["TU", [u]])
        p_ret = min(.60, .36 + (.15 if t in launch_days else 0) + .05 * min(E[t], 2))
        is_ret = rng.random(len(paniers)) < p_ret
        # attribution des clients qui reviennent, taille par taille
        cust = np.full(len(paniers), -1)
        for s in TAILLES + ["TU"]:
            idx = [j for j, b in enumerate(paniers) if b[0] == s and is_ret[j]]
            if not idx:
                continue
            pool = np.arange(n_c) if s == "TU" else np.nonzero(c_size[:n_c] == s)[0]
            w = c_loyal[pool] * np.exp(-(t - c_last[pool]) / 150)
            k = min(len(idx), len(pool))
            if k == 0:
                continue
            chosen = rng.choice(pool, size=k, replace=False, p=w / w.sum())
            cust[idx[:k]] = chosen
        for j, (s, items) in enumerate(paniers):
            retour = cust[j] >= 0
            src = tirer_source(retour, E[t])
            if not retour:
                c = n_c
                n_c += 1
                c_size[c] = s if s != "TU" else rng.choice(TAILLES, p=list(PAYS_T))
                c_loyal[c] = rng.lognormal(0, 1.0)
                c_first[c] = t
                c_pays[c] = rng.choice(list(PAYS), p=list(PAYS.values()))
                c_src[c] = src
                cust[j] = c
            c = cust[j]
            c_last[c] = t
            oid += 1
            brut = net = 0.0
            vc = pd.Series(items).value_counts()
            for vi, qte in vc.items():
                pid = v_pid[vi]
                d = remises[pid][t]
                pu = round(prix[vi] * (1 - d), 2)
                lines.append((oid, variantes.variant_id.iat[vi], pid, v_size[vi], int(qte), prix[vi], d, pu))
                brut += prix[vi] * qte
                net += pu * qte
                if is_jersey[vi] and perso_vid is not None and d < .3:
                    n_perso = int((rng.random(qte) < .18).sum())
                    if n_perso:
                        lines.append((oid, perso_vid, perso_pid, "TU", n_perso, perso_prix, 0.0, perso_prix))
                        brut += perso_prix * n_perso
                        net += perso_prix * n_perso
            port = 0.0 if net >= SEUIL_LIVRAISON_OFFERTE else FRAIS_PORT
            orders.append((oid, int(c) + 1, DAYS[t], src, c_pays[c], int(retour),
                           round(brut, 2), round(brut - net, 2), round(net, 2), round(net / TVA, 2), port))

    commandes = pd.DataFrame(orders, columns=["order_id", "client_id", "date_commande", "source", "pays",
                                              "client_deja_acheteur", "montant_brut_ttc", "remise_ttc",
                                              "montant_net_ttc", "montant_net_ht", "frais_port_ttc"])
    lignes = pd.DataFrame(lines, columns=["order_id", "variant_id", "product_id", "taille", "quantite",
                                          "prix_plein_ttc", "remise_pct", "prix_unitaire_ttc"])
    lignes.insert(0, "line_id", np.arange(1, len(lignes) + 1))
    lignes["montant_ttc"] = (lignes.quantite * lignes.prix_unitaire_ttc).round(2)
    lignes["montant_ht"] = (lignes.montant_ttc / TVA).round(2)
    cout = lignes.product_id.map(p.cout_unitaire_ht)
    lignes["cout_ht"] = (cout * lignes.quantite).round(2)
    lignes["marge_ht"] = (lignes.montant_ht - lignes.cout_ht).round(2)

    clients = pd.DataFrame({
        "client_id": np.arange(1, n_c + 1),
        "taille": c_size[:n_c],
        "pays": c_pays[:n_c],
        "source_acquisition": c_src[:n_c],
        "date_premier_achat": [START + pd.Timedelta(days=int(x)) for x in c_first[:n_c]],
        "client_avant_2025": (np.arange(n_c) < n0).astype(int),
    })
    return commandes, lignes, clients


PAYS_T = list(PART_TAILLE.values())


# ======================================================================================
# 5. Billetterie (événements RÉELS ; ventes jour par jour SIMULÉES)
# ======================================================================================
EVENEMENTS = [
    # id, nom, date, lieu, capacité, ouverture (jours avant), engouement, info réelle
    ("E01", "Inauguration des Arènes (J1)", "2024-09-20", "Les Arènes, Évry", 3000, 45, .70, "4 500 spectateurs réels sur 2 jours"),
    ("E02", "Inauguration des Arènes (J2)", "2024-09-21", "Les Arènes, Évry", 3000, 45, .80, "4 500 spectateurs réels sur 2 jours"),
    ("E03", "KCX 4 - Forever Rivals", "2024-11-09", "Paris La Défense Arena", 30000, 90, .95, "≈ 28 000 spectateurs réels"),
    ("E04", "LEC Roadtrip (J1)", "2025-05-10", "Les Arènes, Évry", 3000, 50, 1.8, "date réelle, ventes simulées"),
    ("E05", "LEC Roadtrip (J2)", "2025-05-11", "Les Arènes, Évry", 3000, 50, 1.6, "date réelle, ventes simulées"),
    ("E06", "Date Arènes 2025 n°3", "2025-06-14", "Les Arènes, Évry", 3000, 40, 1.1, "date hypothétique (5 dates réelles en 2025)"),
    ("E07", "Date Arènes 2025 n°4", "2025-09-27", "Les Arènes, Évry", 3000, 40, 1.2, "date hypothétique (5 dates réelles en 2025)"),
    ("E08", "Date Arènes 2025 n°5", "2025-10-18", "Les Arènes, Évry", 3000, 40, 1.3, "date hypothétique (5 dates réelles en 2025)"),
    ("E09", "KCX 5 (J1) - reporté", "2025-12-19", "Adidas Arena", 7500, 75, 1.0, "report réel annoncé le 12/11/2025, billets remboursés"),
    ("E10", "KCX 5 (J2) - reporté", "2025-12-20", "Adidas Arena", 7500, 75, .9, "report réel annoncé le 12/11/2025, billets remboursés"),
    ("E11", "LEC Roadtrip Spring (J1)", "2026-04-24", "Les Arènes, Évry", 3000, 50, 2.0, "date réelle, ventes simulées"),
    ("E12", "LEC Roadtrip Spring (J2)", "2026-04-25", "Les Arènes, Évry", 3000, 50, 2.3, "date réelle, ventes simulées"),
    ("E13", "LEC Roadtrip Spring (J3)", "2026-04-26", "Les Arènes, Évry", 3000, 50, 2.1, "date réelle, ventes simulées"),
    ("E14", "LEC Roadtrip Summer (J1)", "2026-07-24", "Adidas Arena", 7500, 75, .85, "date réelle ; pass 1 jour restants mi-mai (réel)"),
    ("E15", "LEC Roadtrip Summer (J2)", "2026-07-25", "Adidas Arena", 7500, 75, 1.05, "date réelle ; pass 1 jour restants mi-mai (réel)"),
    ("E16", "LEC Roadtrip Summer (J3)", "2026-07-26", "Adidas Arena", 7500, 75, .95, "date réelle ; pass 1 jour restants mi-mai (réel)"),
]
CATEGORIES = {  # (part de la capacité, prix TTC) — hypothèses
    "Les Arènes, Évry": [("Catégorie 1", .30, 35.0), ("Catégorie 2", .50, 25.0), ("Catégorie 3", .20, 19.0)],
    "Adidas Arena": [("Catégorie 1", .30, 49.0), ("Catégorie 2", .45, 39.0), ("Catégorie 3", .25, 29.0)],
    "Paris La Défense Arena": [("VIP", .03, 150.0), ("Catégorie 1", .27, 60.0), ("Catégorie 2", .40, 45.0), ("Catégorie 3", .30, 30.0)],
}


def simuler_billetterie():
    evts, ventes, attente = [], [], []
    for eid, nom, date, lieu, cap, ouv, hype, info in EVENEMENTS:
        d_evt = pd.Timestamp(date)
        d_ouv = d_evt - pd.Timedelta(days=ouv)
        reporte = "reporté" in nom
        annul = pd.Timestamp("2025-11-12") if reporte else None
        n = ouv + 1
        tau = np.arange(n)
        # arrivées d'acheteurs : ruée le jour J0, décroissance, puis regain la dernière semaine
        forme = .45 * (tau == 0) + .55 * np.exp(-tau / 7) / np.exp(-tau / 7).sum()
        forme += .10 * (tau >= n - 7) / 7
        forme /= forme.sum()
        arrivees = rng.poisson(cap * hype * forme * rng.lognormal(0, .08, n))
        if annul is not None:
            arrivees[(d_ouv + pd.to_timedelta(tau, "D")) > annul] = 0
        restant = {c: int(cap * part) for c, part, _ in CATEGORIES[lieu]}
        prix = {c: px for c, _, px in CATEGORIES[lieu]}
        complet_le = None
        part = {c: p_ for c, p_, _ in CATEGORIES[lieu]}
        for k in range(n):
            demande = int(arrivees[k])
            vendus_jour = {c: 0 for c in restant}
            # la demande se répartit entre les catégories encore ouvertes ; quand l'une est
            # complète, les acheteurs se reportent sur les autres
            for _ in range(4):
                ouvertes = [c for c in restant if restant[c] > 0]
                if demande <= 0 or not ouvertes:
                    break
                tot = sum(part[c] for c in ouvertes)
                alloc = rng.multinomial(demande, [part[c] / tot for c in ouvertes])
                for c, a in zip(ouvertes, alloc):
                    x = min(int(a), restant[c])
                    vendus_jour[c] += x
                    restant[c] -= x
                    demande -= x
            jour = d_ouv + pd.Timedelta(days=k)
            for c, x in vendus_jour.items():
                if x:
                    ventes.append((eid, jour, (d_evt - jour).days, c, x, prix[c], round(x * prix[c], 2), int(reporte)))
            if sum(restant.values()) == 0 and complet_le is None:
                complet_le = jour
            if demande > 0:
                attente.append((eid, jour, int(rng.binomial(demande, .30))))
        vendus = cap - sum(restant.values())
        evts.append((eid, nom, d_evt, lieu, cap, d_ouv, vendus, round(vendus / cap, 4),
                     complet_le, int(reporte), info))
    evenements = pd.DataFrame(evts, columns=["event_id", "nom", "date_evenement", "lieu", "capacite",
                                             "date_ouverture_ventes", "billets_vendus", "taux_remplissage",
                                             "date_complet", "reporte_rembourse", "info_reelle"])
    billets = pd.DataFrame(ventes, columns=["event_id", "date_vente", "jours_avant_evenement", "categorie",
                                            "billets", "prix_ttc", "ca_ttc", "rembourse"])
    liste = pd.DataFrame(attente, columns=["event_id", "date", "inscrits_liste_attente"])
    liste = liste[liste.inscrits_liste_attente > 0]
    return evenements, billets, liste


# ======================================================================================
# 6. Test A/B (page produit du maillot Worlds 2026) — test fictif, pour la méthode
# ======================================================================================
def simuler_ab_test():
    jours = pd.date_range("2026-09-07", "2026-10-04")
    rows = []
    sid = 0
    for d in jours:
        n = rng.poisson(2100 * (1.25 if d.day_of_week >= 5 else 1.0))
        var = rng.choice(["A", "B"], n)
        mobile = rng.random(n) < .78
        src = rng.choice(["instagram", "tiktok", "twitch", "direct", "google", "x"], n,
                         p=[.24, .18, .18, .20, .12, .08])
        p_conv = np.where(var == "A", .030, .034) * np.where(mobile, .9, 1.35)
        conv = rng.random(n) < p_conv
        panier = np.where(conv, np.round(rng.lognormal(np.log(88), .35, n), 2), 0.0)
        for i in range(n):
            sid += 1
            rows.append((sid, d, var[i], "mobile" if mobile[i] else "ordinateur", src[i], int(conv[i]), panier[i]))
    return pd.DataFrame(rows, columns=["session_id", "date", "variante", "appareil", "source", "a_converti", "ca_ttc"])


# ======================================================================================
def main():
    global rng
    produits, variantes = charger_produits()
    E = intensite_evenements()
    lam_base, remises = construire_lambda(produits, variantes, E)

    # calage : CA HT 2025 attendu = cible (deux passes pour tenir compte des ruptures)
    pu_ht = np.stack([remises[pid] for pid in variantes.product_id]) * -1 + 1
    pu_ht *= variantes.product_id.map(produits.set_index("product_id").prix_plein_ttc).values[:, None] / TVA
    m25 = (DAYS.year == 2025)
    scale = TARGET_CA_HT_2025 / (lam_base[:, m25] * pu_ht[:, m25]).sum()
    for _ in range(2):
        rng = np.random.default_rng(SEED)
        lam = lam_base * scale
        q0 = quantites_initiales(produits, variantes, lam)
        ventes, perdues, stock, rupture = simuler_ventes(lam, q0)
        ca25 = (ventes[:, m25] * pu_ht[:, m25]).sum()
        scale *= TARGET_CA_HT_2025 / ca25

    commandes, lignes, clients = construire_commandes(produits, variantes, ventes, remises, E)

    stock_df = variantes[["variant_id", "product_id", "taille"]].copy()
    stock_df["stock_initial"] = np.where(np.isinf(q0), np.nan, q0)
    stock_df["fabrique_a_la_commande"] = np.isinf(q0).astype(int)
    stock_df["unites_vendues"] = ventes.sum(axis=1)
    stock_df["stock_final"] = np.where(np.isinf(stock), np.nan, stock)
    stock_df["date_rupture"] = [DAYS[i] if i >= 0 else pd.NaT for i in rupture]
    stock_df["demande_non_servie_verite"] = perdues.sum(axis=1)   # inobservable en réalité

    # signal observable : alertes « prévenez-moi du retour en stock » (15 % des ventes perdues)
    vi, ti = np.nonzero(perdues)
    alertes = pd.DataFrame({"date": DAYS[ti], "variant_id": variantes.variant_id.values[vi],
                            "product_id": variantes.product_id.values[vi],
                            "alertes": rng.binomial(perdues[vi, ti], .15)})
    alertes = alertes[alertes.alertes > 0]

    rem = pd.DataFrame({pid: remises[pid] for pid in produits.product_id}, index=DAYS)
    rem = rem.stack().rename("remise_pct").reset_index()
    rem.columns = ["date", "product_id", "remise_pct"]
    rem = rem[rem.remise_pct > 0]

    evenements, billets, liste = simuler_billetterie()
    ab = simuler_ab_test()

    sorties = {"sim_produits": produits, "sim_variantes": variantes, "sim_clients": clients,
               "sim_commandes": commandes, "sim_lignes": lignes, "sim_stock": stock_df,
               "sim_alertes_stock": alertes, "sim_remises_jour": rem, "sim_evenements": evenements,
               "sim_billets": billets, "sim_liste_attente": liste, "sim_ab_test": ab}
    for name, df in sorties.items():
        df.to_csv(OUT / f"{name}.csv", index=False, encoding="utf-8", date_format="%Y-%m-%d")
        print(f"{name:20s} {len(df):>8,d} lignes")


if __name__ == "__main__":
    main()
