"""Couche de données pour Power BI (data/powerbi/*.csv) : un schéma en étoile propre.

Question de l'étude : pourquoi la boutique de la KC solde-t-elle l'essentiel de son catalogue
pendant que les grandes tailles sont en rupture, et combien gagnerait-elle à produire chaque
drop au plus juste ?

Faits    : ventes (ligne de commande, SIMULÉ), stock (variante, SIMULÉ), releves (catalogue RÉEL)
Dimensions : produits, tailles, tranches de remise, calendrier, jours depuis le lancement
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_sim as gs  # noqa: E402  (règles de collection, de type et fenêtres de prix)

ROOT = Path(__file__).resolve().parents[1]
CLEAN, OUT, RAW = ROOT / "data" / "clean", ROOT / "data" / "output", ROOT / "data" / "raw" / "boutique"
PBI = ROOT / "data" / "powerbi"
PBI.mkdir(parents=True, exist_ok=True)
FIN = pd.Timestamp("2026-11-08")
TVA = 1.20

TAILLES = ["XS", "S", "M", "L", "XL", "XXL", "3XL", "4XL", "TU"]
TRANCHES = [(0, "Prix plein"), (1, "Moins de 30 %"), (2, "30 à 49 %"), (3, "50 à 69 %"), (4, "70 % et plus")]


def tranche(r: pd.Series) -> pd.Series:
    return pd.cut(r, [-1, 0, .2999, .4999, .6999, 1.01], labels=[t for _, t in TRANCHES]).astype(str)


def periode(d: pd.Series) -> pd.Series:
    out = pd.Series("Hors promotion", index=d.index)
    for a, b in gs.SOLDES:
        out[(d >= a) & (d <= b)] = "Soldes"
    for a, b in (gs.BF_2026,):
        out[(d >= a) & (d <= b)] = "Black Friday"
    return out


# ---------------------------------------------------------------- dimensions
pd.DataFrame({"taille": TAILLES, "ordre": range(len(TAILLES))}).to_csv(PBI / "tailles.csv", index=False)
pd.DataFrame({"tranche_remise": [t for _, t in TRANCHES], "ordre": [o for o, _ in TRANCHES]}).to_csv(PBI / "tranches.csv", index=False)
pd.DataFrame({"jour": range(0, 56)}).to_csv(PBI / "jours_lancement.csv", index=False)

res = pd.read_csv(CLEAN / "kc_resultats_lol.csv", parse_dates=["date"])
res = res[~res.phase.str.startswith("Fin de saison")]
res["type_moment"] = np.select([res.enjeu.fillna("").str.startswith("Qualifiée"), res.phase.eq("Finale"), res.resultat.eq("V")],
                               ["Qualification", "Finale", "Victoire"], "Défaite")
res["libelle"] = res.competition + " · " + res.phase + " · " + res.resultat + " " + res.score_kc.astype(str) + "-" + res.score_adv.astype(str) + " " + res.adversaire.fillna("")
mom = res.groupby("date").agg(match_kc=("libelle", " | ".join), type_moment=("type_moment", "first")).reset_index()
cal = pd.DataFrame({"date": pd.date_range("2025-01-01", "2026-12-31")})
cal["annee"] = cal.date.dt.year
cal["mois"] = cal.date.dt.month
cal["mois_debut"] = cal.date.dt.to_period("M").dt.to_timestamp()
cal["periode_commerciale"] = periode(cal.date)
cal = cal.merge(mom, on="date", how="left")
cal["jour_de_match_kc"] = cal.match_kc.notna().astype(int)
cal.to_csv(PBI / "calendrier.csv", index=False, date_format="%Y-%m-%d")

# ---------------------------------------------------------------- produits
prod = pd.read_csv(CLEAN / "sim_produits.csv", parse_dates=["date_lancement"])
lig = pd.read_csv(CLEAN / "sim_lignes.csv")
com = pd.read_csv(CLEAN / "sim_commandes.csv", parse_dates=["date_commande"])
stock = pd.read_csv(CLEAN / "sim_stock.csv", parse_dates=["date_rupture"])
v = lig.merge(com[["order_id", "date_commande", "client_id", "source", "pays", "client_deja_acheteur"]], on="order_id") \
       .merge(prod[["product_id", "date_lancement", "famille", "cout_unitaire_ht"]], on="product_id")
v["jour_depuis_lancement"] = (v.date_commande - v.date_lancement).dt.days

# jeu de la prévision (mêmes règles que le notebook) : 2025 = entraînement, 2026 = test mis de côté
rupt = stock.merge(prod[["product_id", "date_lancement"]], on="product_id") \
            .assign(r=lambda d: (d.date_rupture - d.date_lancement).dt.days < 55).groupby("product_id").r.mean()
elig = (prod.date_lancement >= "2025-01-01") & (prod.date_lancement + pd.Timedelta(days=55) <= FIN) \
       & (prod.famille != "service") & (prod.precommande == 0) & (prod.product_id.map(rupt).fillna(0) < .5)
prod["jeu_prevision"] = np.where(~elig, "Non éligible", np.where(prod.date_lancement >= "2026-01-01", "Test 2026", "Entraînement 2025"))
prod["origine"] = prod.origine.str.replace("reconstitué (hypothèse)", "reconstitué", regex=False)
FAMILLES = {"maillot": "Maillots", "textile": "Textile", "accessoire": "Accessoires", "cartes": "Cartes et TCG",
            "peluche": "Peluches", "deco": "Déco", "service": "Flocage"}
prod["famille"] = prod.famille.map(FAMILLES)
prod[["product_id", "nom", "type", "famille", "collection", "date_lancement", "prix_plein_ttc", "cout_unitaire_ht",
      "remise_reelle_20261109", "precommande", "origine", "jeu_prevision"]] \
    .to_csv(PBI / "produits.csv", index=False, date_format="%Y-%m-%d")

# ---------------------------------------------------------------- ventes (fait, grain ligne)
v["date"] = v.date_commande
v["periode_commerciale"] = periode(v.date)
v["tranche_remise"] = tranche(v.remise_pct)
v["ca_prix_plein_ht"] = (v.prix_plein_ttc * v.quantite / TVA).round(2)
v["vendu_sous_cout"] = (v.marge_ht < 0).astype(int)
v["client_type"] = np.where(v.client_deja_acheteur == 1, "Déjà client", "Nouveau client")
v[["line_id", "order_id", "date", "client_id", "product_id", "variant_id", "taille", "quantite", "prix_plein_ttc", "remise_pct",
   "tranche_remise", "periode_commerciale", "montant_ht", "ca_prix_plein_ht", "cout_ht", "marge_ht", "vendu_sous_cout",
   "jour_depuis_lancement", "source", "pays", "client_type"]] \
    .to_csv(PBI / "ventes.csv", index=False, date_format="%Y-%m-%d")

# ---------------------------------------------------------------- stock (fait, grain variante)
al = pd.read_csv(CLEAN / "sim_alertes_stock.csv").groupby("variant_id").alertes.sum()
stock["alertes_retour_stock"] = stock.variant_id.map(al).fillna(0).astype(int)
stock["ventes_perdues"] = stock.demande_non_servie_verite
stock[["variant_id", "product_id", "taille", "stock_initial", "fabrique_a_la_commande", "unites_vendues", "stock_final",
       "date_rupture", "ventes_perdues", "alertes_retour_stock"]].to_csv(PBI / "stock.csv", index=False, date_format="%Y-%m-%d")

# ---------------------------------------------------------------- relevés du catalogue (RÉEL)
rel = pd.read_csv(RAW / "variants_snapshots.csv")
rel["taille"] = rel["size"].fillna("TU").replace("", "TU")
rel["type"] = [gs.normalise_type(t, p if isinstance(p, str) else "") for t, p in zip(rel.title, rel.product_type)]
rel["collection"] = rel.title.map(gs.collection)
rel["prix_plein_ttc"] = rel[["price", "compare_at_price"]].max(axis=1)
rel["tranche_remise"] = tranche(rel.discount_pct)
rel["nom"] = rel.title.str.split(r" - (?:Pr.commande|Exp.ditions)", regex=True).str[0]
rel = rel[rel.type != "Service"]
rel[["snapshot_date", "product_id", "variant_id", "nom", "type", "collection", "taille", "prix_plein_ttc", "price",
     "discount_pct", "tranche_remise", "available", "is_preorder"]] \
    .rename(columns={"price": "prix_ttc", "available": "disponible", "is_preorder": "precommande"}) \
    .to_csv(PBI / "releves.csv", index=False)

# ---------------------------------------------------------------- historique RÉEL (archive.org, janv. 2025 -> oct. 2026)
WB = ROOT / "data" / "raw" / "wayback"
if (WB / "captures.csv").exists():
    h = pd.read_csv(WB / "captures.csv", parse_dates=["date"])
    h = h[h.marque.fillna("").str.contains("Karmine", case=False)]           # sans les produits partenaires (Logitech...)
    h["type"] = [gs.normalise_type(t, "") for t in h.titre]
    h["collection"] = h.titre.map(gs.collection)
    h = h[h.type != "Service"]
    h["mois_debut"] = h.date.dt.to_period("M").dt.to_timestamp()
    h["solde"] = (h.remise > 0).astype(int)
    h["tranche_remise"] = tranche(h.remise)
    h.to_csv(PBI / "historique.csv", index=False, date_format="%Y-%m-%d")
    ht = pd.read_csv(WB / "tailles.csv", parse_dates=["date"]).merge(h[["timestamp", "handle", "type", "collection", "mois_debut"]],
                                                                      on=["timestamp", "handle"])
    ht["indisponible"] = 1 - ht.disponible
    ht.to_csv(PBI / "historique_tailles.csv", index=False, date_format="%Y-%m-%d")
    print("Historique :", len(h), "captures,", h.handle.nunique(), "produits,", h.mois_debut.min().date(), "->", h.mois_debut.max().date())
    print((h.groupby("mois_debut").agg(n=("solde", "size"), part_soldes=("solde", "mean"), remise=("remise", lambda r: r[r > 0].median()))).round(2).to_string())
    print((ht.groupby("taille").indisponible.mean()).round(2).to_dict())

# ---------------------------------------------------------------- tables d'analyse (notebook)
pd.read_csv(OUT / "nb_effet_resultats.csv").to_csv(PBI / "effet_moments.csv", index=False)

# chiffres clés pour les titres de page (affichés aussi pour contrôle)
der = rel[rel.snapshot_date == rel.snapshot_date.max()]
pp = der.groupby("product_id").discount_pct.max()
print("Relevé", rel.snapshot_date.max(), ": produits", pp.size, "remisés", f"{(pp > 0).mean():.0%}",
      "remise médiane", f"{der.loc[der.discount_pct > 0, 'discount_pct'].median():.0%}")
print("Épuisées XS / XXL / 3XL :", der[der.taille.isin(["XS", "XXL", "3XL"])].groupby("taille").available.apply(lambda s: f"{1 - s.mean():.0%}").to_dict())
va = v.assign(maillot=v.famille.eq("maillot"))  # famille brute (avant libellés)
print("Part CA prix plein maillots", f"{va[va.maillot & va.remise_pct.eq(0)].montant_ht.sum() / va[va.maillot].montant_ht.sum():.0%}",
      "| autres", f"{va[~va.maillot & va.remise_pct.eq(0)].montant_ht.sum() / va[~va.maillot].montant_ht.sum():.0%}")
print("Manque à gagner remises (HT, période)", round(v.ca_prix_plein_ht.sum() - v.montant_ht.sum()))
print("Fichiers écrits dans", PBI)
