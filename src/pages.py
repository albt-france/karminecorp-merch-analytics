"""Les 7 pages du rapport d'analyse, organisées autour d'UNE question :

    Pourquoi la boutique de la KC solde-t-elle près des trois quarts de son catalogue pendant que
    les grandes tailles sont en rupture, et combien gagnerait-elle à produire chaque drop au plus juste ?

Chaque page répond à une sous-question avec des KPI, des filtres et des visuels calculés en direct.
Les titres (conclusions) et les textes sont écrits à partir des données, au moment de la génération.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from design import GAP, H_FILTRES, H_KPI, LARGEUR, MARGE, Y_FILTRES, Carte, Page, colonnes

ROOT = Path(__file__).resolve().parents[1]
PBI, OUT, CLEAN = ROOT / "data" / "powerbi", ROOT / "data" / "output", ROOT / "data" / "clean"
Y_BAS = 996


def fr(x: float, dec: int = 0) -> str:
    return f"{x:,.{dec}f}".replace(",", " ").replace(".", ",")


def pct(x: float) -> str:
    return f"{x * 100:.0f} %"


@lru_cache
def chiffres() -> dict:
    c = {}
    rel = pd.read_csv(PBI / "releves.csv")
    der = rel[rel.snapshot_date == rel.snapshot_date.max()]
    pp = der.groupby("product_id").discount_pct.max()
    c["date_releve"] = der.snapshot_date.iloc[0]
    c["n_produits"], c["part_soldes"] = pp.size, (pp > 0).mean()
    c["remise_max"] = der.discount_pct.max()
    ep = 1 - der.groupby("taille").disponible.mean()
    c["ep_xs"], c["ep_grand"] = ep["XS"], 1 - der[der.taille.isin(["XXL", "3XL"])].disponible.mean()
    h = pd.read_csv(PBI / "historique.csv", parse_dates=["mois_debut"])
    m = h.groupby("mois_debut").solde.mean()
    c["hist_debut"], c["hist_fin"] = m.iloc[:3].mean(), m.iloc[-3:].mean()
    c["hist_n"] = len(h)
    if c["hist_debut"] < .05:
        c["titre_constat"] = f"Prix plein jusqu'à fin 2025, puis les soldes : {pct(c['part_soldes'])} du catalogue soldé le 9/11"
    elif c["hist_fin"] > c["hist_debut"] + .1:
        c["titre_constat"] = (f"Les soldes gagnent le catalogue : {pct(c['hist_debut'])} des pages début 2025, "
                              f"{pct(c['part_soldes'])} des produits le 9/11")
    else:
        c["titre_constat"] = f"{pct(c['part_soldes'])} du catalogue est soldé, et les grandes tailles manquent depuis 2025"
    v = pd.read_csv(PBI / "ventes.csv", low_memory=False)
    c["manque_periode"] = v.ca_prix_plein_ht.sum() - v.montant_ht.sum()
    sc = pd.read_csv(OUT / "nb_prevision_scores.csv", index_col=0).wape
    c["wape"] = sc.min()
    c["k"] = float(sc.idxmin().split("x")[1].rstrip(")")) if "x" in sc.idxmin() else 3.5
    pr = pd.read_csv(PBI / "produits.csv", parse_dates=["date_lancement"], low_memory=False)
    fen = pr[(pr.date_lancement >= "2025-01-01") & (pr.date_lancement <= "2026-09-14") & (pr.famille != "Flocage")].product_id.astype(str)
    vv = v[v.product_id.astype(str).isin(set(fen))]
    j = vv.jour_depuis_lancement
    c["part_j3"] = vv.loc[j.between(0, 3), "quantite"].sum() / vv.loc[j.between(0, 55), "quantite"].sum()   # même calcul que la mesure DAX
    g = pd.read_csv(OUT / "gains_estimes.csv")
    st = g[g.levier.str.startswith("Stock")]
    arr = lambda x: int(x / 10_000 + 0.5) * 10
    c["gain_bas"], c["gain_haut"] = arr(st.gain_bas.sum()), arr(st.gain_haut.sum())
    eff = pd.read_csv(OUT / "nb_effet_resultats.csv").set_index("moment")
    c["effet_qualif"] = eff.loc["Qualification", "hausse_ca_j0_j3"]
    s = pd.read_csv(PBI / "stock.csv").merge(pd.read_csv(PBI / "produits.csv")[["product_id", "famille"]], on="product_id")
    s = s[s.famille.isin(["Maillots", "Textile"]) & (s.fabrique_a_la_commande == 0) & ~s.taille.isin(["TU", "4XL"])]
    c["ventes_perdues"] = s.ventes_perdues.sum()
    return c


def grille(avec_filtres: bool = True) -> tuple[int, int, int]:
    """(y des KPI, y de la 1re rangée, hauteur d'une rangée)."""
    y_kpi = Y_FILTRES + H_FILTRES + GAP if avec_filtres else Y_FILTRES
    y1 = y_kpi + H_KPI + GAP
    return y_kpi, y1, (Y_BAS - y1 - GAP) // 2


def kpis(y: int, specs: list[tuple]) -> list[Carte]:
    return [Carte(x, y, w, H_KPI, titre=t, tags=tags, style="kpi", visuel=vid)
            for (x, w), (vid, t, tags) in zip(colonnes([1] * len(specs)), specs)]


def filtres(ids: list[str]) -> Carte:
    return Carte(MARGE, Y_FILTRES, LARGEUR, H_FILTRES, style="filtres", filtres=ids)


SRC_REEL = "Source : relevé quotidien de karminecorp.fr (RÉEL)"
SRC_SIM = "Ventes et stocks simulés, calés sur le catalogue réel (SIMULÉ)"


# ======================================================================================
def page_0() -> Page:
    c = chiffres()
    y_kpi, y1, hr = grille(False)
    (xa, wa), (xb, wb) = colonnes([1, 1])
    return Page(
        numero=0, rubrique="Étude de cas · merch de la Karmine Corp", nom_onglet="0 · Synthèse",
        titre=f"Pourquoi la boutique solde-t-elle {pct(c['part_soldes'])} de son catalogue ?",
        question="Et combien la KC gagnerait-elle à produire chaque drop au plus juste ? Analyse en 6 pages.",
        tags=("RÉEL", "SIMULÉ", "ESTIMATION"),
        sources="Sources et hypothèses : data/SOURCES.md · SQL (DuckDB), Python, Power BI",
        cartes=kpis(y_kpi, [("kpi_soldes", "Produits soldés", ("RÉEL",)),
                            ("kpi_grandes_tailles", "XXL et 3XL épuisées", ("RÉEL",)),
                            ("kpi_ca_2025", "CA merch 2025 HT", ("SIMULÉ",)),
                            ("kpi_manque_an", "Remises accordées / an", ("SIMULÉ",)),
                            ("kpi_gain_total", "Gain estimé / an", ("ESTIMATION",))])
        + [Carte(xa, y1, wa, hr, titre="Le problème", style="texte", visuel="txt_probleme"),
           Carte(xb, y1, wb, hr, titre="CA mensuel : prix plein ou remisé", legende="CA HT par mois, selon la remise accordée",
                 tags=("SIMULÉ",), visuel="ca_mensuel_tranche_p0"),
           Carte(xa, y1 + hr + GAP, wa, hr, titre="La réponse, page par page", style="texte", visuel="txt_reponse"),
           Carte(xb, y1 + hr + GAP, wb, hr, titre="Données et méthode", style="texte", visuel="txt_methode")],
        textes={
            "txt_probleme": [
                ("Le merch pèse environ 40 % du chiffre d'affaires de la KC (2,5 M€ en 2023, Sheep Esports). "
                 f"Le {c['date_releve'][8:]}/{c['date_releve'][5:7]}/2026, {pct(c['part_soldes'])} des {c['n_produits']} produits "
                 f"de la boutique sont soldés, jusqu'à -{c['remise_max'] * 100:.0f} %, alors que {pct(c['ep_grand'])} des variantes "
                 f"XXL et 3XL sont épuisées, contre {pct(c['ep_xs'])} des XS.", False),
                ("Autrement dit : on solde ce qu'on a trop produit et on manque ce qui se vend. Ce rapport mesure d'où "
                 "vient ce décalage, ce qu'il coûte et comment le réduire.", False),
                ("Le 5 octobre 2026, la KC a annoncé vouloir renforcer son équipe merch : c'est le bon moment pour "
                 "piloter les drops par la donnée.", True)],
            "txt_reponse": [
                ("01 · Le constat (réel) : 22 mois d'historique du catalogue (archive.org) et le relevé du jour.", False),
                ("02 · Les ventes : les maillots de saison s'écoulent, les capsules restent en stock et finissent soldées.", False),
                (f"03 · Un drop : {pct(c['part_j3'])} des 8 premières semaines se vendent en 4 jours, ce qui permet de "
                 f"prévoir la suite ({pct(c['wape'])} d'erreur sur les drops 2026).", False),
                ("04 · Les tailles : la courbe commandée est trop centrée, les XXL et 3XL manquent.", False),
                ("05 · Les remises : passé -50 %, la marge s'effondre.", False),
                (f"06 · La recommandation : produire au plus juste rapporterait {c['gain_bas']} à {c['gain_haut']} k€ par an.", True)],
            "txt_methode": [
                ("RÉEL · Catalogue de karminecorp.fr (prix, remises, disponibilité par taille) : pages archivées par archive.org "
                 "de janvier 2025 à octobre 2026, et relevé du 9/11/2026 ; résultats sportifs 2025-2026.", False),
                ("SIMULÉ · Ventes, stocks et clients 2025-2026 (graine fixe), calés sur le catalogue réel et les ordres "
                 "de grandeur publiés. Ce ne sont pas des données de la KC.", False),
                ("MÉTHODE · SQL (DuckDB) ; Python (prévision validée sur les drops 2026 mis de côté, régression aux erreurs "
                 "robustes) ; Power BI (modèle en étoile, mesures DAX, paramètres de simulation). "
                 "Claude Code m'a assisté sur une partie des scripts, pour gagner en efficacité.", False)],
        })


def page_1() -> Page:
    c = chiffres()
    y_kpi, y1, hr = grille()
    (xa, wa), (xb, wb) = colonnes([2, 1])
    (x1, w1), (x2, w2), (x3, w3) = colonnes([1, 1, 1])
    return Page(
        numero=1, rubrique="Page 01 · Le constat", nom_onglet="1 · Le constat",
        titre=c["titre_constat"],
        question="Que montre le catalogue réel ? 22 mois de pages archivées (janvier 2025 - octobre 2026) et le relevé du 9 novembre 2026.",
        tags=("RÉEL",), sources="Sources : pages produit archivées par archive.org et relevé de karminecorp.fr (RÉEL)",
        cartes=[filtres(["f_type_hist", "f_collection_hist"])]
        + kpis(y_kpi, [("kpi_hist_captures", "Pages archivées analysées", ("RÉEL",)),
                       ("kpi_hist_soldes", "Pages soldées (historique)", ("RÉEL",)),
                       ("kpi_part_soldes", "Produits soldés le 9/11", ("RÉEL",)),
                       ("kpi_grandes_tailles_p1", "XXL et 3XL épuisées le 9/11", ("RÉEL",))])
        + [Carte(xa, y1, wa, hr, titre="Aucune remise en 2025, des soldes massifs au printemps 2026",
                 legende="Part des pages produit soldées (bleu) et remise médiane des produits soldés (gris), par mois",
                 tags=("RÉEL",), visuel="hist_mois"),
           Carte(xb, y1, wb, hr, titre="Sur 22 mois, les grandes tailles manquent",
                 legende="Part des tailles indisponibles sur les pages archivées", tags=("RÉEL",), visuel="hist_tailles"),
           Carte(x1, y1 + hr + GAP, w1, hr, titre="Le 9/11 : surtout des remises profondes",
                 legende="Nombre de variantes par tranche de remise", tags=("RÉEL",), visuel="rel_tranches"),
           Carte(x2, y1 + hr + GAP, w2, hr, titre="Le 9/11 : toutes les collections soldées",
                 legende="Part des produits soldés, par collection", tags=("RÉEL",), visuel="rel_collections"),
           Carte(x3, y1 + hr + GAP, w3, hr, titre="Le 9/11 : les plus fortes remises",
                 legende="Produits classés par remise (prix TTC)", tags=("RÉEL",), visuel="rel_table")])


def page_2() -> Page:
    y_kpi, y1, hr = grille()
    (xa, wa), (xb, wb) = colonnes([2, 1])
    return Page(
        numero=2, rubrique="Page 02 · Les ventes", nom_onglet="2 · Les ventes",
        titre="Les maillots de saison s'écoulent, les capsules restent en stock",
        question="Où se fait le chiffre d'affaires, et quels drops s'écoulent vraiment ? Janvier 2025 à novembre 2026.",
        tags=("SIMULÉ",), sources=SRC_SIM,
        cartes=[filtres(["f_annee", "f_famille", "f_periode"])]
        + kpis(y_kpi, [("kpi_ca", "CA HT", ("SIMULÉ",)), ("kpi_marge", "Taux de marge", ("SIMULÉ",)),
                       ("kpi_prix_plein", "Part du CA au prix plein", ("SIMULÉ",)), ("kpi_panier", "Panier moyen HT", ("SIMULÉ",))])
        + [Carte(xa, y1, wa, hr, titre="Prix plein en 2025, remises en 2026",
                 legende="CA HT par mois, selon la remise accordée (bleu : prix plein)", tags=("SIMULÉ",), visuel="ca_mensuel_tranche"),
           Carte(xb, y1, wb, hr, titre="Les maillots font la moitié du CA", legende="CA HT par famille de produits",
                 tags=("SIMULÉ",), visuel="ca_famille"),
           Carte(xa, y1 + hr + GAP, wa, hr, titre="Collections : qui s'écoule, qui reste en stock ?",
                 legende="CA, marge, part vendue au prix plein et écoulement du stock, par collection", tags=("SIMULÉ",), visuel="matrice_collections"),
           Carte(xb, y1 + hr + GAP, wb, hr, titre="Plus la remise est forte, moins on marge", legende="Taux de marge HT par tranche de remise",
                 tags=("SIMULÉ",), visuel="marge_tranche_p2")])


def page_3() -> Page:
    c = chiffres()
    y_kpi, y1, hr = grille()
    (xa, wa), (xb, wb) = colonnes([1, 1])
    (xc, wc), (xd, wd) = colonnes([2, 1])
    return Page(
        numero=3, rubrique="Page 03 · Anatomie d'un drop", nom_onglet="3 · Un drop",
        titre="Un drop se joue en 4 jours, ce qui permet de prévoir ses 8 semaines",
        question="Comment se vend un drop, et peut-on prévoir ses ventes dès les premiers jours ? Prévision validée sur les drops 2026.",
        tags=("SIMULÉ", "RÉEL"), sources=SRC_SIM + " · résultats sportifs Wikipedia (RÉEL)",
        cartes=[filtres(["f_collection", "f_famille_drop"])]
        + kpis(y_kpi, [("kpi_part_j03", "Ventes faites entre J0 et J3", ("SIMULÉ",)),
                       ("kpi_ratio", "Ratio 8 semaines / J0-J3", ("SIMULÉ",)),
                       ("kpi_wape", "Erreur sur les drops 2026", ("SIMULÉ",)),
                       ("kpi_produits_test", "Produits mis de côté (test)", ("SIMULÉ",))])
        + [Carte(xa, y1, wa, hr, titre="Une courbe de lancement très concentrée",
                 legende="Part cumulée des 8 premières semaines (bleu : sélection, gris : toutes collections)", tags=("SIMULÉ",), visuel="courbe"),
           Carte(xb, y1, wb, hr, titre="Les 4 premiers jours prédisent la suite",
                 legende="Ventes J0-J3 et ventes à 8 semaines, par produit (bleu : drops 2026 mis de côté)", tags=("SIMULÉ",), visuel="nuage_prevision"),
           Carte(xc, y1 + hr + GAP, wc, hr, titre=f"Prévision des drops 2026 : règle × {fr(c['k'], 1)}",
                 legende="Ventes J0-J3, prévision à 8 semaines et ventes réelles, produits lancés en 2026", tags=("SIMULÉ",), visuel="table_prevision"),
           Carte(xd, y1 + hr + GAP, wd, hr, titre="Quand lancer : après une qualification",
                 legende="Hausse du CA sur J0-J3 (régression, calendrier réel)", tags=("RÉEL", "SIMULÉ"), visuel="effet_moments")])


def page_4() -> Page:
    y_kpi, y1, hr = grille()
    (x1, w1), (x2, w2), (x3, w3) = colonnes([2, 1, 1])
    (xa, wa), (xb, wb) = colonnes([2, 1])
    return Page(
        numero=4, rubrique="Page 04 · Les tailles", nom_onglet="4 · Les tailles",
        titre="On commande trop de XS, et pas assez de XXL et de 3XL",
        question="La courbe de tailles produite suit-elle la demande ? Maillots et textile produits à l'avance.",
        tags=("SIMULÉ", "RÉEL"), sources=SRC_SIM + " · ruptures réelles : relevé de karminecorp.fr",
        cartes=[filtres(["f_famille_taille", "f_collection_taille"])]
        + kpis(y_kpi, [("kpi_ecoul_xs", "Stock écoulé en XS", ("SIMULÉ",)), ("kpi_ecoul_3xl", "Stock écoulé en 3XL", ("SIMULÉ",)),
                       ("kpi_ventes_perdues", "Ventes perdues (ruptures)", ("SIMULÉ",)), ("kpi_ca_perdu", "CA perdu par les ruptures", ("SIMULÉ",))])
        + [Carte(x1, y1, w1, hr, titre="La production est trop centrée", legende="Part de chaque taille : production (gris) et demande (bleu)",
                 tags=("SIMULÉ",), visuel="prod_demande"),
           Carte(x2, y1, w2, hr, titre="Les grandes tailles s'écoulent", legende="Part du stock vendue, par taille",
                 tags=("SIMULÉ",), visuel="ecoulement_taille"),
           Carte(x3, y1, w3, hr, titre="Ce que montre la boutique", legende="Variantes épuisées le jour du relevé",
                 tags=("RÉEL",), visuel="rel_tailles_p4"),
           Carte(xa, y1 + hr + GAP, wa, hr, titre="Écoulement par collection et par taille",
                 legende="Part du stock vendue (plus c'est bleu, plus la taille s'est vendue)", tags=("SIMULÉ",), visuel="matrice_tailles"),
           Carte(xb, y1 + hr + GAP, wb, hr, titre="Les ruptures coûtent des ventes", legende="Ventes perdues par taille, en pièces",
                 tags=("SIMULÉ",), visuel="perdues_taille")])


def page_5() -> Page:
    c = chiffres()
    y_kpi, y1, hr = grille()
    (x1, w1), (x2, w2), (x3, w3) = colonnes([1, 1, 1])
    (xa, wa), (xb, wb) = colonnes([1, 1])
    return Page(
        numero=5, rubrique="Page 05 · Le coût des remises", nom_onglet="5 · Les remises",
        titre="Solder le surstock coûte cher : passé -50 %, la marge disparaît",
        question=f"Combien coûtent les remises, et à partir de quand détruisent-elles la marge ? {fr(c['manque_periode'] / 1000)} k€ de remises accordées en 22 mois.",
        tags=("SIMULÉ",), sources=SRC_SIM,
        cartes=[filtres(["f_periode_remise", "f_collection_remise"])]
        + kpis(y_kpi, [("kpi_manque", "Remises accordées (HT)", ("SIMULÉ",)), ("kpi_remise_moy", "Remise moyenne", ("SIMULÉ",)),
                       ("kpi_sous_cout", "Pièces vendues sous le coût", ("SIMULÉ",)), ("kpi_stock_restant", "Stock restant (au coût)", ("SIMULÉ",))])
        + [Carte(x1, y1, w1, hr, titre="La marge s'effondre après -50 %", legende="Taux de marge HT par tranche de remise",
                 tags=("SIMULÉ",), visuel="marge_tranche"),
           Carte(x2, y1, w2, hr, titre="Des remises concentrées sur deux moments", legende="Remise moyenne accordée, par mois",
                 tags=("SIMULÉ",), visuel="remise_mois"),
           Carte(x3, y1, w3, hr, titre="Ce qui reste en stock", legende="Valeur du stock restant au coût, par collection",
                 tags=("SIMULÉ",), visuel="stock_collection"),
           Carte(xa, y1 + hr + GAP, wa, hr, titre="Les remises touchent toutes les collections", legende="Remises accordées (HT), par collection",
                 tags=("SIMULÉ",), visuel="manque_collection"),
           Carte(xb, y1 + hr + GAP, wb, hr, titre="Les produits vendus à perte", legende="Pièces vendues sous leur coût et marge perdue",
                 tags=("SIMULÉ",), visuel="table_perte")])


def page_6() -> Page:
    c = chiffres()
    y_kpi, y1, hr = grille()
    (xa, wa), (xb, wb) = colonnes([1, 1])
    return Page(
        numero=6, rubrique="Page 06 · La recommandation", nom_onglet="6 · La recommandation",
        titre=f"Produire au plus juste rapporterait {c['gain_bas']} à {c['gain_haut']} k€ par an",
        question="Combien rapporterait un pilotage des drops par la donnée ? Réglez les deux hypothèses avec les filtres ci-dessous.",
        tags=("ESTIMATION",), sources="Estimation à partir des ventes simulées · hypothèses détaillées dans notebooks/analyse.ipynb",
        cartes=[filtres(["f_recuperation", "f_surplus"])]
        + kpis(y_kpi, [("kpi_gain_tailles", "Gain courbe de tailles / an", ("ESTIMATION",)),
                       ("kpi_gain_production", "Gain production au plus juste / an", ("ESTIMATION",)),
                       ("kpi_gain_total_p6", "Gain total / an", ("ESTIMATION",)),
                       ("kpi_roi", "Gain / coût d'un analyste (60 k€)", ("ESTIMATION",))])
        + [Carte(xa, y1, wa, hr, titre="D'où vient le gain", legende="Gain annuel par levier, selon les hypothèses choisies",
                 tags=("ESTIMATION",), visuel="gains_leviers"),
           Carte(xb, y1, wb, hr, titre="Comment le gain est calculé", style="texte", visuel="txt_calcul"),
           Carte(xa, y1 + hr + GAP, wa, hr, titre="Recommandations", style="texte", visuel="txt_reco"),
           Carte(xb, y1 + hr + GAP, wb, hr, titre="Plan des 90 premiers jours", style="texte", visuel="txt_plan")],
        textes={
            "txt_calcul": [
                (f"Courbe de tailles · ventes perdues par rupture ({fr(c['ventes_perdues'])} pièces en 22 mois) × part récupérée "
                 "× marge d'une pièce vendue au prix plein, ramené à 12 mois.", False),
                ("Production au plus juste · surplus (pièces soldées à -50 % ou plus, et stock restant) × part évitée grâce "
                 "à la prévision J0-J3 × coût non engagé, net du prix de solde.", False),
                ("Hypothèse basse : 50 % des ventes perdues récupérées et 10 % du surplus évité. Hypothèse haute : 100 % "
                 "et 25 %. Sans sélection, les montants affichés sont ceux de l'hypothèse basse.", True)],
            "txt_reco": [
                (f"1 · Prévoir chaque drop dès ses 4 premiers jours (ventes à 8 semaines ≈ {fr(c['k'], 1)} × J0-J3) et "
                 "réassortir à J4, au lieu de tout produire avant le lancement.", False),
                ("2 · Commander la courbe de tailles de la demande : plus de XXL et de 3XL, moins de XS, d'après les "
                 "ventes et les alertes « retour en stock ».", False),
                ("3 · Éviter les remises profondes : passé -50 %, une pièce ne rapporte presque plus rien. Mieux vaut "
                 "un stock initial plus petit.", False),
                (f"4 · Caler les lancements sur les moments sportifs : une qualification fait +{c['effet_qualif'] * 100:.0f} % "
                 "de CA sur 4 jours.", False)],
            "txt_plan": [
                ("J1-30 · Brancher Shopify et le stock, définir les indicateurs (écoulement, part au prix plein, ventes "
                 "perdues), premier tableau de bord des drops.", False),
                ("J31-60 · Prévision J0-J3 sur chaque drop, courbe de tailles par famille, alertes de rupture.", False),
                ("J61-90 · Test A/B sur une page produit, bilan chiffré des premiers gains, feuille de route 2027.", False)],
        })


PAGES = {0: page_0, 1: page_1, 2: page_2, 3: page_3, 4: page_4, 5: page_5, 6: page_6}
