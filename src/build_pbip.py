"""Génère le projet Power BI (PBIP) : modèle sémantique en TMDL + rapport d'analyse en PBIR.

    python src/prep_powerbi.py      # couche de données (data/powerbi)
    python src/build_pbip.py        # projet powerbi/BlueWall.pbip   (option --page N : page ouverte)

Fermer Power BI Desktop avant de relancer : tout le projet est réécrit.
À la première ouverture, cliquer sur « Actualiser maintenant » pour charger les CSV.
"""
from __future__ import annotations

import json
import shutil
import sys
import uuid
from pathlib import Path

import pandas as pd

import design as ds
from pages import PAGES

ROOT = Path(__file__).resolve().parents[1]
PBI = ROOT / "powerbi"
NOM = "BlueWall"
SM, RP = PBI / f"{NOM}.SemanticModel", PBI / f"{NOM}.Report"
BASE_THEME = Path(r"C:\rovio-case-study\powerbi\RovioCaseStudy.Report\StaticResources\SharedResources\BaseThemes\Fluent2-CY26SU10.json")
DOSSIER = str(ROOT / "data" / "powerbi") + "\\"
M = "_Mesures"
BLEU, GRIS_BARRE, GRIS_CLAIR, BLANC, GRIS_TXT, FOND_TAB = ds.HEX(ds.BLEU), "#5A5A60", "#8C8C92", "#FFFFFF", "#AAAAAA", "#16171B"
FAM = '{ "Maillots", "Textile" }'

# ======================================================================================
# 1. Modèle sémantique (TMDL)
# ======================================================================================
# nom, fichier, colonnes date, formats, tri (colonne -> colonne de tri)
TABLES = [
    ("Ventes", "ventes.csv", ["date"], {"remise_pct": "0 %", "montant_ht": "#,0.00 €"}, {}),
    ("Stock", "stock.csv", ["date_rupture"], {}, {}),
    ("Releves", "releves.csv", ["snapshot_date"], {"discount_pct": "0 %", "prix_ttc": "#,0.00 €", "prix_plein_ttc": "#,0.00 €"}, {}),
    ("Produits", "produits.csv", ["date_lancement"], {"prix_plein_ttc": "#,0.00 €", "cout_unitaire_ht": "#,0.00 €"}, {}),
    ("Tailles", "tailles.csv", [], {}, {"taille": "ordre"}),
    ("Tranches", "tranches.csv", [], {}, {"tranche_remise": "ordre"}),
    ("Calendrier", "calendrier.csv", ["date", "mois_debut"], {"mois_debut": "mmm yy", "annee": "0"}, {}),
    ("Jours lancement", "jours_lancement.csv", [], {}, {}),
    ("Effet moments", "effet_moments.csv", [], {"hausse_ca_j0_j3": "+0 %;-0 %;0 %"}, {}),
    ("Historique", "historique.csv", ["date", "mois_debut"], {"remise": "0 %", "mois_debut": "mmm yy"}, {}),
    ("Historique tailles", "historique_tailles.csv", ["date", "mois_debut"], {}, {}),
]
PARAMS = [  # tables de paramètres (simulation « what-if »), générées en M
    ("Param recuperation", "part_recuperee", "List.Transform({0..10}, each _ / 10)"),
    ("Param surplus", "part_evitee", "List.Transform({0..10}, each _ / 20)"),
]
RELATIONS = [("Ventes.product_id", "Produits.product_id"), ("Ventes.taille", "Tailles.taille"),
             ("Ventes.tranche_remise", "Tranches.tranche_remise"), ("Ventes.date", "Calendrier.date"),
             ("Stock.product_id", "Produits.product_id"), ("Stock.taille", "Tailles.taille"),
             ("Releves.taille", "Tailles.taille"), ("Releves.tranche_remise", "Tranches.tranche_remise"),
             ("'Historique tailles'.taille", "Tailles.taille")]

WIN = ("KEEPFILTERS ( Produits[date_lancement] >= DATE ( 2025, 1, 1 ) && Produits[date_lancement] <= DATE ( 2026, 9, 14 ) ), "
       "KEEPFILTERS ( Produits[famille] <> \"Flocage\" )")
D = "VAR d = [Date retenue] RETURN "
MESURES = [
    # --- Ventes
    ("CA HT", "SUM ( Ventes[montant_ht] )", "#,0 €", "1 Ventes"),
    ("Marge HT", "SUM ( Ventes[marge_ht] )", "#,0 €", "1 Ventes"),
    ("Taux de marge", "DIVIDE ( [Marge HT], [CA HT] )", "0 %", "1 Ventes"),
    ("Unités", "SUM ( Ventes[quantite] )", "#,0", "1 Ventes"),
    ("Commandes", "DISTINCTCOUNT ( Ventes[order_id] )", "#,0", "1 Ventes"),
    ("Panier moyen HT", "DIVIDE ( [CA HT], [Commandes] )", "#,0.00 €", "1 Ventes"),
    ("CA au prix plein HT", "SUM ( Ventes[ca_prix_plein_ht] )", "#,0 €", "1 Ventes"),
    ("Remises accordées", "[CA au prix plein HT] - [CA HT]", "#,0 €", "1 Ventes"),
    ("Remise moyenne", "DIVIDE ( [Remises accordées], [CA au prix plein HT] )", "0 %", "1 Ventes"),
    ("Part du CA au prix plein", "DIVIDE ( CALCULATE ( [CA HT], Ventes[remise_pct] = 0 ), [CA HT] )", "0 %", "1 Ventes"),
    ("Part des unités au prix plein", "DIVIDE ( CALCULATE ( [Unités], Ventes[remise_pct] = 0 ), [Unités] )", "0 %", "1 Ventes"),
    ("Pièces vendues sous le coût", "CALCULATE ( [Unités], Ventes[vendu_sous_cout] = 1 )", "#,0", "1 Ventes"),
    ("Marge perdue sous le coût", "- CALCULATE ( [Marge HT], Ventes[vendu_sous_cout] = 1 )", "#,0 €", "1 Ventes"),
    ("CA merch 2025", "CALCULATE ( [CA HT], Calendrier[annee] = 2025 )", "#,0 €", "1 Ventes"),
    ("Remises accordées par an", "CALCULATE ( [Remises accordées], REMOVEFILTERS ( Calendrier ) ) * 12 / 22.25", "#,0 €", "1 Ventes"),
    # --- Drops et prévision
    ("Unités J0-J3", "CALCULATE ( [Unités], Ventes[jour_depuis_lancement] >= 0, Ventes[jour_depuis_lancement] <= 3 )", "#,0", "2 Drops"),
    ("Unités J0-J55", "CALCULATE ( [Unités], Ventes[jour_depuis_lancement] >= 0, Ventes[jour_depuis_lancement] <= 55 )", "#,0", "2 Drops"),
    ("Part des ventes J0-J3", f"CALCULATE ( DIVIDE ( [Unités J0-J3], [Unités J0-J55] ), {WIN} )", "0 %", "2 Drops"),
    ("Part cumulée des ventes", "VAR j = MAX ( 'Jours lancement'[jour] ) RETURN CALCULATE ( DIVIDE ( CALCULATE ( [Unités], "
     f"Ventes[jour_depuis_lancement] >= 0, Ventes[jour_depuis_lancement] <= j ), [Unités J0-J55] ), {WIN} )", "0 %", "2 Drops"),
    ("Part cumulée (toutes collections)", "CALCULATE ( [Part cumulée des ventes], REMOVEFILTERS ( Produits[collection] ), "
     "REMOVEFILTERS ( Produits[famille] ) )", "0 %", "2 Drops"),
    ("Ratio 8 semaines / J0-J3", "CALCULATE ( MEDIANX ( FILTER ( ALL ( Produits[product_id], Produits[jeu_prevision] ), "
     "Produits[jeu_prevision] = \"Entraînement 2025\" ), DIVIDE ( [Unités J0-J55], [Unités J0-J3] ) ), REMOVEFILTERS ( Produits ) )", "0.0", "2 Drops"),
    ("Prévision à 8 semaines", "[Unités J0-J3] * [Ratio 8 semaines / J0-J3]", "#,0", "2 Drops"),
    ("Écart de prévision", "DIVIDE ( [Prévision à 8 semaines] - [Unités J0-J55], [Unités J0-J55] )", "+0 %;-0 %;0 %", "2 Drops"),
    ("Erreur sur les drops 2026", "VAR k = [Ratio 8 semaines / J0-J3] VAR t = CALCULATETABLE ( VALUES ( Produits[product_id] ), "
     "Produits[jeu_prevision] = \"Test 2026\" ) RETURN DIVIDE ( SUMX ( t, ABS ( [Unités J0-J3] * k - [Unités J0-J55] ) ), "
     "SUMX ( t, [Unités J0-J55] ) )", "0 %", "2 Drops"),
    ("Produits mis de côté", "CALCULATE ( DISTINCTCOUNT ( Produits[product_id] ), Produits[jeu_prevision] = \"Test 2026\" )", "#,0", "2 Drops"),
    ("Hausse du CA J0-J3", "SUM ( 'Effet moments'[hausse_ca_j0_j3] )", "+0 %;-0 %;0 %", "2 Drops"),
    # --- Stock et tailles
    ("Stock initial", "SUM ( Stock[stock_initial] )", "#,0", "3 Stock"),
    ("Pièces vendues sur stock", "CALCULATE ( SUM ( Stock[unites_vendues] ), Stock[fabrique_a_la_commande] = 0 )", "#,0", "3 Stock"),
    ("Taux d'écoulement", "DIVIDE ( [Pièces vendues sur stock], [Stock initial] )", "0 %", "3 Stock"),
    ("Écoulement XS", f"CALCULATE ( [Taux d'écoulement], Tailles[taille] = \"XS\", KEEPFILTERS ( Produits[famille] IN {FAM} ) )", "0 %", "3 Stock"),
    ("Écoulement 3XL", f"CALCULATE ( [Taux d'écoulement], Tailles[taille] = \"3XL\", KEEPFILTERS ( Produits[famille] IN {FAM} ) )", "0 %", "3 Stock"),
    ("Stock restant", "CALCULATE ( SUM ( Stock[stock_final] ), Stock[fabrique_a_la_commande] = 0 )", "#,0", "3 Stock"),
    ("Stock restant au coût", "SUMX ( FILTER ( Stock, Stock[fabrique_a_la_commande] = 0 ), Stock[stock_final] * RELATED ( Produits[cout_unitaire_ht] ) )", "#,0 €", "3 Stock"),
    ("Ventes perdues", "CALCULATE ( SUM ( Stock[ventes_perdues] ), Stock[fabrique_a_la_commande] = 0 )", "#,0", "3 Stock"),
    ("Ventes perdues textile", f"CALCULATE ( [Ventes perdues], KEEPFILTERS ( Produits[famille] IN {FAM} ), KEEPFILTERS ( NOT Tailles[taille] IN {{ \"TU\", \"4XL\" }} ) )", "#,0", "3 Stock"),
    ("CA perdu par les ruptures", "SUMX ( FILTER ( Stock, Stock[fabrique_a_la_commande] = 0 ), Stock[ventes_perdues] * RELATED ( Produits[prix_plein_ttc] ) / 1.2 )", "#,0 €", "3 Stock"),
    ("CA perdu textile", f"CALCULATE ( [CA perdu par les ruptures], KEEPFILTERS ( Produits[famille] IN {FAM} ), KEEPFILTERS ( NOT Tailles[taille] IN {{ \"TU\", \"4XL\" }} ) )", "#,0 €", "3 Stock"),
    ("Alertes retour en stock", "SUM ( Stock[alertes_retour_stock] )", "#,0", "3 Stock"),
    ("Part de la production", "DIVIDE ( [Stock initial], CALCULATE ( [Stock initial], ALLSELECTED ( Tailles ) ) )", "0 %", "3 Stock"),
    ("Part de la demande", "DIVIDE ( [Pièces vendues sur stock] + [Ventes perdues], CALCULATE ( [Pièces vendues sur stock] + [Ventes perdues], ALLSELECTED ( Tailles ) ) )", "0 %", "3 Stock"),
    # --- Relevés réels du catalogue
    ("Date retenue", "IF ( ISFILTERED ( Releves[snapshot_date] ), MAX ( Releves[snapshot_date] ), CALCULATE ( MAX ( Releves[snapshot_date] ), REMOVEFILTERS ( Releves ) ) )", "dd/mm/yyyy", "4 Relevés"),
    ("Produits en ligne", D + "CALCULATE ( DISTINCTCOUNT ( Releves[product_id] ), Releves[snapshot_date] = d )", "#,0", "4 Relevés"),
    ("Produits soldés", D + "CALCULATE ( DISTINCTCOUNT ( Releves[product_id] ), Releves[snapshot_date] = d, Releves[discount_pct] > 0 )", "#,0", "4 Relevés"),
    ("Part des produits soldés", "DIVIDE ( [Produits soldés], [Produits en ligne] )", "0 %", "4 Relevés"),
    ("Remise médiane", D + "CALCULATE ( MEDIAN ( Releves[discount_pct] ), Releves[snapshot_date] = d, Releves[discount_pct] > 0 )", "0 %", "4 Relevés"),
    ("Variantes", D + "CALCULATE ( COUNTROWS ( Releves ), Releves[snapshot_date] = d )", "#,0", "4 Relevés"),
    ("Variantes épuisées", D + "CALCULATE ( COUNTROWS ( Releves ), Releves[snapshot_date] = d, Releves[disponible] = 0 )", "#,0", "4 Relevés"),
    ("Part des variantes épuisées", "DIVIDE ( [Variantes épuisées], [Variantes] )", "0 %", "4 Relevés"),
    ("Grandes tailles épuisées", "CALCULATE ( [Part des variantes épuisées], Tailles[taille] IN { \"XXL\", \"3XL\" } )", "0 %", "4 Relevés"),
    ("Prix plein TTC (relevé)", D + "CALCULATE ( MAX ( Releves[prix_plein_ttc] ), Releves[snapshot_date] = d )", "#,0.00 €", "4 Relevés"),
    ("Prix TTC (relevé)", D + "CALCULATE ( MIN ( Releves[prix_ttc] ), Releves[snapshot_date] = d )", "#,0.00 €", "4 Relevés"),
    ("Remise (relevé)", D + "CALCULATE ( MAX ( Releves[discount_pct] ), Releves[snapshot_date] = d )", "0 %", "4 Relevés"),
    # --- Historique réel (archive.org)
    ("Pages archivées analysées", "COUNTROWS ( Historique )", "#,0", "4 Relevés"),
    ("Part des pages soldées", "IF ( COUNTROWS ( Historique ) >= 10, AVERAGE ( Historique[solde] ) )", "0 %", "4 Relevés"),
    ("Remise médiane (historique)", "CALCULATE ( MEDIAN ( Historique[remise] ), Historique[remise] > 0 )", "0 %", "4 Relevés"),
    ("Tailles indisponibles (historique)", "AVERAGE ( 'Historique tailles'[indisponible] )", "0 %", "4 Relevés"),
    # --- Simulation des gains (what-if)
    ("Part des ventes perdues récupérée", "SELECTEDVALUE ( 'Param recuperation'[part_recuperee], 0.5 )", "0 %", "5 Gains"),
    ("Part du surplus évitée", "SELECTEDVALUE ( 'Param surplus'[part_evitee], 0.1 )", "0 %", "5 Gains"),
    ("Marge par pièce au prix plein", f"CALCULATE ( DIVIDE ( [Marge HT], [Unités] ), Ventes[remise_pct] = 0, Produits[famille] IN {FAM} )", "#,0.00 €", "5 Gains"),
    ("Gain courbe de tailles", f"CALCULATE ( [Ventes perdues], Produits[famille] IN {FAM}, NOT Tailles[taille] IN {{ \"TU\", \"4XL\" }} ) "
     "* [Marge par pièce au prix plein] * [Part des ventes perdues récupérée] * 12 / 22.25", "#,0 €", "5 Gains"),
    ("Gain production au plus juste",
     f"VAR fam = TREATAS ( {FAM}, Produits[famille] ) "
     "VAR nliq = CALCULATE ( [Unités], Ventes[remise_pct] >= 0.5, fam ) "
     "VAR prixSolde = DIVIDE ( CALCULATE ( [CA HT], Ventes[remise_pct] >= 0.5, fam ), nliq ) "
     "VAR nstk = CALCULATE ( [Stock restant], fam ) "
     "VAR cout = DIVIDE ( CALCULATE ( SUMX ( FILTER ( Stock, Stock[fabrique_a_la_commande] = 0 ), Stock[stock_initial] * RELATED ( Produits[cout_unitaire_ht] ) ), fam ), CALCULATE ( [Stock initial], fam ) ) "
     "RETURN ( nliq * MAX ( cout - prixSolde, 0 ) + nstk * cout ) * [Part du surplus évitée] * 12 / 22.25", "#,0 €", "5 Gains"),
    ("Gain total", "[Gain courbe de tailles] + [Gain production au plus juste]", "#,0 €", "5 Gains"),
    ("Gain par rapport au coût", "DIVIDE ( [Gain total], 60000 )", '0.0"×"', "5 Gains"),
]


def q(name: str) -> str:
    return f"'{name}'" if any(ch in name for ch in " -()éèàêçÉ%€/'") else name


def qdax(name: str) -> str:
    return "'" + name.replace("'", "''") + "'" if any(ch in name for ch in " -()éèàêçÉ%€/'") else name


def colonnes(path: Path, dates: list[str]) -> list[tuple[str, str]]:
    df = pd.read_csv(path, low_memory=False)
    out = []
    for c in df.columns:
        if c in dates:
            out.append((c, "date"))
        elif pd.api.types.is_integer_dtype(df[c]):
            out.append((c, "int"))
        elif pd.api.types.is_numeric_dtype(df[c]):
            out.append((c, "num"))
        else:
            out.append((c, "text"))
    return out


M_TYPE = {"int": "Int64.Type", "num": "type number", "date": "type date", "text": "type text"}
T_TYPE = {"int": "int64", "num": "double", "date": "dateTime", "text": "string"}


def ecrire(path: Path, txt: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(txt, encoding="utf-8", newline="\r\n")


def bloc_colonne(c, t, fmt=None, tri=None, source=None):
    lines = [f"\tcolumn {q(c)}", f"\t\tdataType: {T_TYPE[t]}"]
    fmt = fmt or ("dd/mm/yyyy" if t == "date" else None)
    if fmt:
        lines.append(f"\t\tformatString: {fmt}")
    lines += ["\t\tsummarizeBy: none", f"\t\tsourceColumn: {source or c}"]
    if tri:
        lines.append(f"\t\tsortByColumn: {tri}")
    if t == "date":
        lines += ["", "\t\tannotation UnderlyingDateTimeDataType = Date"]
    return lines + [""]


def table_tmdl(nom, fichier, dates, formats, tri) -> str:
    cols = colonnes(ROOT / "data" / "powerbi" / fichier, dates)
    lines = [f"table {q(nom)}", ""]
    for c, t in cols:
        lines += bloc_colonne(c, t, formats.get(c), tri.get(c))
    types = ", ".join(f'{{"{c}", {M_TYPE[t]}}}' for c, t in cols)
    lines += [f"\tpartition {q(nom)} = m", "\t\tmode: import", "\t\tsource =", "\t\t\t\tlet",
              f'\t\t\t\t\tSource = Csv.Document(File.Contents(DossierDonnees & "{fichier}"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),',
              "\t\t\t\t\tPromoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),",
              f'\t\t\t\t\tTyped = Table.TransformColumnTypes(Promoted, {{{types}}}, "en-US")',
              "\t\t\t\tin", "\t\t\t\t\tTyped", ""]
    return "\n".join(lines)


def param_tmdl(nom, col, liste) -> str:
    lines = [f"table {q(nom)}", ""] + bloc_colonne(col, "num", "0 %")
    lines += [f"\tpartition {q(nom)} = m", "\t\tmode: import", "\t\tsource =", "\t\t\t\tlet",
              f"\t\t\t\t\tSource = Table.FromList({liste}, Splitter.SplitByNothing(), {{\"{col}\"}}),",
              f'\t\t\t\t\tTyped = Table.TransformColumnTypes(Source, {{{{"{col}", type number}}}})',
              "\t\t\t\tin", "\t\t\t\t\tTyped", ""]
    return "\n".join(lines)


def mesures_tmdl() -> str:
    lines = [f"table {M}", ""]
    for nom, dax, fmt, dossier in MESURES:
        lines.append(f"\tmeasure {qdax(nom)} = {dax}")
        if fmt:
            lines.append(f"\t\tformatString: {fmt}")
        lines += [f"\t\tdisplayFolder: {dossier}", ""]
    lines += ["\tcolumn _", "\t\tdataType: string", "\t\tisHidden", "\t\tsummarizeBy: none", "\t\tsourceColumn: _", "",
              f"\tpartition {M} = m", "\t\tmode: import", "\t\tsource = #table(type table [_ = text], {})", ""]
    return "\n".join(lines)


def ecrire_modele():
    if SM.exists():
        shutil.rmtree(SM)
    d = SM / "definition"
    ecrire(SM / "definition.pbism", json.dumps({"version": "4.2", "settings": {}}, indent=2))
    ecrire(SM / ".platform", json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "SemanticModel", "displayName": NOM}, "config": {"version": "2.0", "logicalId": str(uuid.uuid4())}}, indent=2))
    ecrire(d / "database.tmdl", "database\n\tcompatibilityLevel: 1606\n")
    noms = [t[0] for t in TABLES] + [p[0] for p in PARAMS] + [M]
    model = ["model Model", "\tculture: fr-FR", "\tdefaultPowerBIDataSourceVersion: powerBI_V3", "\tsourceQueryCulture: fr-FR",
             "\tdataAccessOptions", "\t\tlegacyRedirects", "\t\treturnErrorValuesAsNull", "",
             "annotation __PBI_TimeIntelligenceEnabled = 0", "",
             "annotation PBI_QueryOrder = " + json.dumps(noms + ["DossierDonnees"], ensure_ascii=False), ""]
    model += [f"ref table {q(n)}" for n in noms] + [""]
    ecrire(d / "model.tmdl", "\n".join(model))
    ecrire(d / "expressions.tmdl", f'expression DossierDonnees = "{DOSSIER}" meta [IsParameterQuery=true, Type="Text", '
                                   'IsParameterQueryRequired=true]\n\n\tannotation PBI_ResultType = Text\n')
    rel = []
    for i, (a, b) in enumerate(RELATIONS, 1):
        rel += [f"relationship rel_{i:02d}", f"\tfromColumn: {a}", f"\ttoColumn: {b}", ""]
    ecrire(d / "relationships.tmdl", "\n".join(rel))
    for t in TABLES:
        ecrire(d / "tables" / f"{t[0]}.tmdl", table_tmdl(*t))
    for p in PARAMS:
        ecrire(d / "tables" / f"{p[0]}.tmdl", param_tmdl(*p))
    ecrire(d / "tables" / f"{M}.tmdl", mesures_tmdl())


# ======================================================================================
# 2. Rapport (PBIR)
# ======================================================================================
VC_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.4.0/schema.json"
PAGE_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"
PAGES_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json"


def raw(v):
    if isinstance(v, bool):
        s = "true" if v else "false"
    elif isinstance(v, (int, float)):
        s = f"{v}D"
    else:
        s = "'" + str(v).replace("'", "''") + "'"
    return {"Literal": {"Value": s}}


def lit(v):
    return {"expr": raw(v)}


def color(h):
    return {"solid": {"color": lit(h)}}


def col(t, c):
    return {"Column": {"Expression": {"SourceRef": {"Entity": t}}, "Property": c}}


def mes(n):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": M}}, "Property": n}}


def qref(f):
    if "Column" in f:
        return f'{f["Column"]["Expression"]["SourceRef"]["Entity"]}.{f["Column"]["Property"]}'
    return f'{M}.{f["Measure"]["Property"]}'


def proj(f, label=None):
    p = {"field": f, "queryRef": qref(f), "nativeQueryRef": f["Column"]["Property"] if "Column" in f else f["Measure"]["Property"]}
    if label:
        p["displayName"] = label
    return p


def serie_mesure(f, h):
    return {"properties": {"fill": color(h)}, "selector": {"metadata": qref(f)}}


def serie_valeur(t, c, valeur, h):
    return {"properties": {"fill": color(h)},
            "selector": {"data": [{"scopeId": {"Comparison": {"ComparisonKind": 0, "Left": col(t, c), "Right": raw(valeur)}}}]}}


def filtre(t, c, valeurs, inclure=True):
    cond = {"In": {"Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "t"}}, "Property": c}}],
                   "Values": [[raw(v)] for v in valeurs]}}
    if not inclure:
        cond = {"Not": {"Expression": cond}}
    return {"name": f"f_{c}_{len(valeurs)}_{int(inclure)}", "type": "Categorical", "field": col(t, c),
            "filter": {"Version": 2, "From": [{"Name": "t", "Entity": t, "Type": 0}], "Where": [{"Condition": cond}]}}


SANS_TAILLE_TU = filtre("Tailles", "taille", ["TU", "4XL"], False)
TEXTILE = filtre("Produits", "famille", ["Maillots", "Textile"])
AXE = lambda show=True, start=None: {"properties": {"show": lit(show), "labelColor": color(GRIS_TXT), "fontSize": lit(11),
                                                     **({"start": lit(start)} if start is not None else {})}}
LABELS = lambda show=True: {"properties": {"show": lit(show), "color": color(BLANC), "fontSize": lit(11)}}
LEG = lambda show=False: [{"properties": {"show": lit(show), "position": lit("Top"), "labelColor": color(GRIS_TXT), "fontSize": lit(11)}}]
TABLE_STYLE = {
    "values": [{"properties": {"fontSize": lit(11), "fontColorPrimary": color(BLANC), "backColorPrimary": color(FOND_TAB),
                               "fontColorSecondary": color(BLANC), "backColorSecondary": color(FOND_TAB)}}],
    "columnHeaders": [{"properties": {"fontSize": lit(11), "fontColor": color(GRIS_TXT), "backColor": color(FOND_TAB)}}],
    "grid": [{"properties": {"gridVertical": lit(False), "gridHorizontal": lit(True), "gridHorizontalColor": color("#2E2F35"), "rowPadding": lit(4)}}],
}


def chaleur(f, bas="#1E1F24", haut=BLEU):
    """Mise en forme conditionnelle (fond) en dégradé sur une valeur de matrice ou de tableau."""
    regle = {"min": {"color": raw(bas)}, "max": {"color": raw(haut)}, "nullColoringStrategy": {"strategy": raw("asZero")}}
    return {"properties": {"backColor": {"solid": {"color": {"expr": {"FillRule": {"Input": f, "FillRule": {"linearGradient2": regle}}}}}}},
            "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": qref(f)}}


class Rapport:
    def __init__(self):
        self.visuels = []

    def ajouter(self, vid, zone, visual, filtres=None):
        x, y, w, h = zone
        n = len(self.visuels) + 1
        vc = {"$schema": VC_SCHEMA, "name": vid,
              "position": {"x": round(x), "y": round(y), "z": n * 1000, "height": round(h), "width": round(w), "tabOrder": n * 1000},
              "visual": visual}
        if filtres:
            vc["filterConfig"] = {"filters": filtres}
        self.visuels.append(vc)


def conteneur():
    return {"title": [{"properties": {"show": lit(False)}}], "subTitle": [{"properties": {"show": lit(False)}}],
            "background": [{"properties": {"show": lit(False)}}], "border": [{"properties": {"show": lit(False)}}],
            "visualHeader": [{"properties": {"show": lit(False)}}], "padding": [{"properties": {"top": lit(2), "bottom": lit(2), "left": lit(2), "right": lit(2)}}]}


def graphe(vtype, roles, objects=None, labels=None, tri=None):
    labels = labels or {}
    v = {"visualType": vtype,
         "query": {"queryState": {r: {"projections": [proj(f, labels.get(qref(f))) for f in fs]} for r, fs in roles.items() if fs}},
         "drillFilterOtherVisuals": True, "visualContainerObjects": conteneur()}
    if tri:
        v["query"]["sortDefinition"] = {"sort": [{"field": tri[0], "direction": tri[1]}], "isDefaultSort": False}
    if objects:
        v["objects"] = objects
    return v


def carte_kpi(mesure):
    return graphe("card", {"Values": [mes(mesure)]},
                  {"labels": [{"properties": {"color": color(BLANC), "fontSize": lit(26), "labelDisplayUnits": lit(1),
                                              "fontFamily": lit("Segoe UI Semibold")}}],
                   "categoryLabels": [{"properties": {"show": lit(False)}}]})


def segment(champ, titre, unique=False):
    objs = {"data": [{"properties": {"mode": lit("Dropdown")}}],
            "header": [{"properties": {"show": lit(True), "fontColor": color(GRIS_TXT), "textSize": lit(10)}}],
            "items": [{"properties": {"fontColor": color(BLANC), "background": color(FOND_TAB), "textSize": lit(11)}}]}
    if unique:
        objs["selection"] = [{"properties": {"singleSelect": lit(True)}}]
    return graphe("slicer", {"Values": [champ]}, objs, labels={qref(champ): titre})


def zone_texte(paragraphes):
    paras = []
    for i, (txt, gras) in enumerate(paragraphes):
        if i:
            paras.append({"textRuns": [{"value": "", "textStyle": {"fontSize": "6pt"}}]})
        runs = []
        if " · " in txt[:16]:
            tete, reste = txt.split(" · ", 1)
            runs.append({"value": tete + "  ", "textStyle": {"fontSize": "12pt", "color": BLEU, "fontWeight": "bold"}})
            txt = reste
        runs.append({"value": txt, "textStyle": {"fontSize": "12pt", "color": BLANC, **({"fontWeight": "bold"} if gras else {})}})
        paras.append({"textRuns": runs})
    return {"visualType": "textbox", "objects": {"general": [{"properties": {"paragraphs": paras}}]},
            "visualContainerObjects": {"background": [{"properties": {"show": lit(False)}}], "border": [{"properties": {"show": lit(False)}}]}}


# ---------------------------------------------------------------- catalogue des visuels
KPI = {
    "kpi_soldes": "Part des produits soldés", "kpi_grandes_tailles": "Grandes tailles épuisées", "kpi_ca_2025": "CA merch 2025",
    "kpi_manque_an": "Remises accordées par an", "kpi_gain_total": "Gain total",
    "kpi_produits_ligne": "Produits en ligne", "kpi_hist_captures": "Pages archivées analysées",
    "kpi_hist_soldes": "Part des pages soldées", "kpi_grandes_tailles_p1": "Grandes tailles épuisées", "kpi_part_soldes": "Part des produits soldés", "kpi_remise_mediane": "Remise médiane",
    "kpi_epuisees": "Part des variantes épuisées",
    "kpi_ca": "CA HT", "kpi_marge": "Taux de marge", "kpi_prix_plein": "Part du CA au prix plein", "kpi_panier": "Panier moyen HT",
    "kpi_part_j03": "Part des ventes J0-J3", "kpi_ratio": "Ratio 8 semaines / J0-J3", "kpi_wape": "Erreur sur les drops 2026",
    "kpi_produits_test": "Produits mis de côté",
    "kpi_ecoul_xs": "Écoulement XS", "kpi_ecoul_3xl": "Écoulement 3XL", "kpi_ventes_perdues": "Ventes perdues textile",
    "kpi_ca_perdu": "CA perdu textile",
    "kpi_manque": "Remises accordées", "kpi_remise_moy": "Remise moyenne", "kpi_sous_cout": "Pièces vendues sous le coût",
    "kpi_stock_restant": "Stock restant au coût",
    "kpi_gain_tailles": "Gain courbe de tailles", "kpi_gain_production": "Gain production au plus juste",
    "kpi_gain_total_p6": "Gain total", "kpi_roi": "Gain par rapport au coût",
}
SEGMENTS = {
    "f_date_releve": (col("Releves", "snapshot_date"), "Date du relevé", True),
    "f_type_releve": (col("Releves", "type"), "Type de produit", False),
    "f_collection_releve": (col("Releves", "collection"), "Collection", False),
    "f_type_hist": (col("Historique", "type"), "Type de produit (historique)", False),
    "f_collection_hist": (col("Historique", "collection"), "Collection (historique)", False),
    "f_annee": (col("Calendrier", "annee"), "Année", False),
    "f_famille": (col("Produits", "famille"), "Famille", False),
    "f_periode": (col("Calendrier", "periode_commerciale"), "Période commerciale", False),
    "f_collection": (col("Produits", "collection"), "Collection", False),
    "f_famille_drop": (col("Produits", "famille"), "Famille", False),
    "f_famille_taille": (col("Produits", "famille"), "Famille", False),
    "f_collection_taille": (col("Produits", "collection"), "Collection", False),
    "f_periode_remise": (col("Calendrier", "periode_commerciale"), "Période commerciale", False),
    "f_collection_remise": (col("Produits", "collection"), "Collection", False),
    "f_recuperation": (col("Param recuperation", "part_recuperee"), "Ventes perdues récupérées", True),
    "f_surplus": (col("Param surplus", "part_evitee"), "Surplus évité", True),
}
TRANCHE_COULEURS = [("Prix plein", BLEU), ("Moins de 30 %", "#7AA2F0"), ("30 à 49 %", GRIS_CLAIR), ("50 à 69 %", GRIS_BARRE), ("70 % et plus", "#3A3B41")]


def visuel(vid):
    """Renvoie (visual, filtres) pour chaque identifiant de pages.py."""
    if vid in KPI:
        return carte_kpi(KPI[vid]), None
    if vid in SEGMENTS:
        champ, titre, unique = SEGMENTS[vid]
        return segment(champ, titre, unique), None
    ca = mes("CA HT")
    if vid.startswith("ca_mensuel_tranche"):
        return graphe("columnChart", {"Category": [col("Calendrier", "mois_debut")], "Y": [ca], "Series": [col("Tranches", "tranche_remise")]},
                      {"dataPoint": [serie_valeur("Tranches", "tranche_remise", v, h) for v, h in TRANCHE_COULEURS],
                       "categoryAxis": [AXE()], "valueAxis": [AXE()], "legend": LEG(True), "labels": [LABELS(False)]},
                      labels={qref(ca): "CA HT", "Tranches.tranche_remise": "Remise", "Calendrier.mois_debut": "Mois"}), \
            [filtre("Calendrier", "mois_debut", [], False)] if False else None
    if vid == "ca_famille":
        return graphe("clusteredBarChart", {"Category": [col("Produits", "famille")], "Y": [ca]},
                      {"dataPoint": [{"properties": {"fill": color(BLEU)}}], "labels": [LABELS()], "categoryAxis": [AXE()],
                       "valueAxis": [AXE(False)], "legend": LEG()}, tri=(ca, "Descending")), None
    if vid == "matrice_collections":
        vals = [ca, mes("Taux de marge"), mes("Part des unités au prix plein"), mes("Taux d'écoulement")]
        objs = dict(TABLE_STYLE)
        objs["rowHeaders"] = [{"properties": {"fontSize": lit(11), "fontColor": color(BLANC), "backColor": color(FOND_TAB)}}]
        objs["subTotals"] = [{"properties": {"rowSubtotals": lit(False), "columnSubtotals": lit(False)}}]
        objs["values"] = objs["values"] + [chaleur(mes("Part des unités au prix plein"), "#3A3B41", BLEU)]
        return graphe("pivotTable", {"Rows": [col("Produits", "collection")], "Values": vals}, objs,
                      labels={"Produits.collection": "Collection", f"{M}.Part des unités au prix plein": "Part au prix plein",
                              f"{M}.Taux d'écoulement": "Stock écoulé"}, tri=(ca, "Descending")), None
    if vid.startswith("marge_tranche"):
        f = mes("Taux de marge")
        return graphe("clusteredColumnChart", {"Category": [col("Tranches", "tranche_remise")], "Y": [f]},
                      {"dataPoint": [{"properties": {"fill": color(BLEU)}}], "labels": [LABELS()], "categoryAxis": [AXE()],
                       "valueAxis": [AXE(False)], "legend": LEG()}, tri=(col("Tranches", "tranche_remise"), "Ascending")), None
    # --- page 1 (relevés réels)
    if vid == "rel_tranches":
        f = mes("Variantes")
        return graphe("clusteredColumnChart", {"Category": [col("Tranches", "tranche_remise")], "Y": [f]},
                      {"dataPoint": [{"properties": {"fill": color(BLEU)}}], "labels": [LABELS()], "categoryAxis": [AXE()],
                       "valueAxis": [AXE(False)], "legend": LEG()}, tri=(col("Tranches", "tranche_remise"), "Ascending")), None
    if vid == "rel_collections":
        f = mes("Part des produits soldés")
        return graphe("clusteredBarChart", {"Category": [col("Releves", "collection")], "Y": [f]},
                      {"dataPoint": [{"properties": {"fill": color(BLEU)}}], "labels": [LABELS()], "categoryAxis": [AXE()],
                       "valueAxis": [AXE(False)], "legend": LEG()}, tri=(f, "Descending")), None
    if vid in ("rel_tailles", "rel_tailles_p4"):
        f = mes("Part des variantes épuisées")
        return graphe("clusteredColumnChart", {"Category": [col("Tailles", "taille")], "Y": [f]},
                      {"dataPoint": [{"properties": {"fill": color(BLANC if vid.endswith("p4") else BLEU)}}], "labels": [LABELS()],
                       "categoryAxis": [AXE()], "valueAxis": [AXE(False)], "legend": LEG()},
                      tri=(col("Tailles", "taille"), "Ascending")), [SANS_TAILLE_TU]
    if vid == "rel_table":
        cols = [col("Releves", "nom"), col("Releves", "collection"), mes("Prix plein TTC (relevé)"), mes("Prix TTC (relevé)"), mes("Remise (relevé)")]
        objs = dict(TABLE_STYLE)
        objs["total"] = [{"properties": {"totals": lit(False)}}]
        return graphe("tableEx", {"Values": cols}, objs,
                      labels={"Releves.nom": "Produit", "Releves.collection": "Collection", f"{M}.Prix plein TTC (relevé)": "Prix plein",
                              f"{M}.Prix TTC (relevé)": "Prix", f"{M}.Remise (relevé)": "Remise"},
                      tri=(mes("Remise (relevé)"), "Descending")), None
    if vid == "rel_matrice":
        f = mes("Part des variantes épuisées")
        objs = dict(TABLE_STYLE)
        objs["rowHeaders"] = [{"properties": {"fontSize": lit(11), "fontColor": color(BLANC), "backColor": color(FOND_TAB)}}]
        objs["subTotals"] = [{"properties": {"rowSubtotals": lit(False), "columnSubtotals": lit(False)}}]
        objs["values"] = objs["values"] + [chaleur(f)]
        return graphe("pivotTable", {"Rows": [col("Releves", "type")], "Columns": [col("Tailles", "taille")], "Values": [f]}, objs,
                      labels={"Releves.type": "Type", "Tailles.taille": "Taille", qref(f): "Épuisées"}), [SANS_TAILLE_TU]
    if vid == "hist_mois":
        a, b = mes("Part des pages soldées"), mes("Remise médiane (historique)")
        return graphe("lineChart", {"Category": [col("Historique", "mois_debut")], "Y": [a, b]},
                      {"dataPoint": [serie_mesure(a, BLEU), serie_mesure(b, GRIS_CLAIR)], "categoryAxis": [AXE()],
                       "valueAxis": [AXE(True, 0)], "legend": LEG(True), "lineStyles": [{"properties": {"strokeWidth": lit(3)}}],
                       "labels": [LABELS(False)]},
                      labels={qref(a): "Pages soldées", qref(b): "Remise médiane", "Historique.mois_debut": "Mois"}), None
    if vid == "hist_tailles":
        f = mes("Tailles indisponibles (historique)")
        return graphe("clusteredColumnChart", {"Category": [col("Tailles", "taille")], "Y": [f]},
                      {"dataPoint": [{"properties": {"fill": color(BLEU)}}], "labels": [LABELS()], "categoryAxis": [AXE()],
                       "valueAxis": [AXE(False)], "legend": LEG()}, tri=(col("Tailles", "taille"), "Ascending")), [SANS_TAILLE_TU]
    # --- page 3 (drops)
    if vid == "courbe":
        a, b = mes("Part cumulée des ventes"), mes("Part cumulée (toutes collections)")
        return graphe("lineChart", {"Category": [col("Jours lancement", "jour")], "Y": [b, a]},
                      {"dataPoint": [serie_mesure(a, BLEU), serie_mesure(b, GRIS_CLAIR)], "categoryAxis": [AXE()],
                       "valueAxis": [AXE(True, 0)], "legend": LEG(True), "lineStyles": [{"properties": {"strokeWidth": lit(3)}}]},
                      labels={qref(a): "Sélection", qref(b): "Toutes collections", "Jours lancement.jour": "Jours depuis le lancement"}), None
    if vid == "nuage_prevision":
        x, y = mes("Unités J0-J3"), mes("Unités J0-J55")
        return graphe("scatterChart", {"Category": [col("Produits", "nom")], "X": [x], "Y": [y], "Series": [col("Produits", "jeu_prevision")]},
                      {"dataPoint": [serie_valeur("Produits", "jeu_prevision", "Test 2026", BLEU),
                                     serie_valeur("Produits", "jeu_prevision", "Entraînement 2025", GRIS_CLAIR)],
                       "categoryAxis": [AXE()], "valueAxis": [AXE()], "legend": LEG(True), "markers": [{"properties": {"markerSize": lit(6)}}]},
                      labels={qref(x): "Ventes J0-J3", qref(y): "Ventes à 8 semaines", "Produits.jeu_prevision": "Jeu"}), \
            [filtre("Produits", "jeu_prevision", ["Non éligible"], False)]
    if vid == "table_prevision":
        cols = [col("Produits", "nom"), col("Produits", "collection"), mes("Unités J0-J3"), mes("Prévision à 8 semaines"),
                mes("Unités J0-J55"), mes("Écart de prévision")]
        objs = dict(TABLE_STYLE)
        objs["total"] = [{"properties": {"totals": lit(False)}}]
        return graphe("tableEx", {"Values": cols}, objs,
                      labels={"Produits.nom": "Produit", "Produits.collection": "Collection", f"{M}.Unités J0-J3": "Ventes J0-J3",
                              f"{M}.Prévision à 8 semaines": "Prévision 8 sem.", f"{M}.Unités J0-J55": "Réel 8 sem.",
                              f"{M}.Écart de prévision": "Écart"}, tri=(mes("Unités J0-J55"), "Descending")), \
            [filtre("Produits", "jeu_prevision", ["Test 2026"])]
    if vid == "effet_moments":
        f = mes("Hausse du CA J0-J3")
        return graphe("clusteredBarChart", {"Category": [col("Effet moments", "moment")], "Y": [f]},
                      {"dataPoint": [{"properties": {"fill": color(BLEU)}}], "labels": [LABELS()], "categoryAxis": [AXE()],
                       "valueAxis": [AXE(False)], "legend": LEG()}, tri=(f, "Descending")), \
            [filtre("Effet moments", "moment", ["Lancement d'une collection (J0-J3)"], False)]
    # --- page 4 (tailles)
    if vid == "prod_demande":
        a, b = mes("Part de la production"), mes("Part de la demande")
        return graphe("clusteredColumnChart", {"Category": [col("Tailles", "taille")], "Y": [a, b]},
                      {"dataPoint": [serie_mesure(a, GRIS_BARRE), serie_mesure(b, BLEU)], "labels": [LABELS()], "categoryAxis": [AXE()],
                       "valueAxis": [AXE(False)], "legend": LEG(True)},
                      labels={qref(a): "Production", qref(b): "Demande"}, tri=(col("Tailles", "taille"), "Ascending")), [SANS_TAILLE_TU, TEXTILE]
    if vid == "ecoulement_taille":
        f = mes("Taux d'écoulement")
        return graphe("clusteredColumnChart", {"Category": [col("Tailles", "taille")], "Y": [f]},
                      {"dataPoint": [{"properties": {"fill": color(BLEU)}}], "labels": [LABELS()], "categoryAxis": [AXE()],
                       "valueAxis": [AXE(False)], "legend": LEG()}, tri=(col("Tailles", "taille"), "Ascending")), [SANS_TAILLE_TU, TEXTILE]
    if vid == "matrice_tailles":
        f = mes("Taux d'écoulement")
        objs = dict(TABLE_STYLE)
        objs["rowHeaders"] = [{"properties": {"fontSize": lit(11), "fontColor": color(BLANC), "backColor": color(FOND_TAB)}}]
        objs["subTotals"] = [{"properties": {"rowSubtotals": lit(False), "columnSubtotals": lit(False)}}]
        objs["values"] = objs["values"] + [chaleur(f)]
        return graphe("pivotTable", {"Rows": [col("Produits", "collection")], "Columns": [col("Tailles", "taille")], "Values": [f]}, objs,
                      labels={"Produits.collection": "Collection", "Tailles.taille": "Taille", qref(f): "Écoulé"}), [SANS_TAILLE_TU, TEXTILE]
    if vid == "perdues_taille":
        f = mes("Ventes perdues")
        return graphe("clusteredColumnChart", {"Category": [col("Tailles", "taille")], "Y": [f]},
                      {"dataPoint": [{"properties": {"fill": color(BLEU)}}], "labels": [LABELS()], "categoryAxis": [AXE()],
                       "valueAxis": [AXE(False)], "legend": LEG()}, tri=(col("Tailles", "taille"), "Ascending")), [SANS_TAILLE_TU, TEXTILE]
    # --- page 5 (remises)
    if vid == "remise_mois":
        f = mes("Remise moyenne")
        return graphe("lineChart", {"Category": [col("Calendrier", "mois_debut")], "Y": [f]},
                      {"dataPoint": [{"properties": {"fill": color(BLEU)}}], "categoryAxis": [AXE()], "valueAxis": [AXE(True, 0)],
                       "legend": LEG(), "lineStyles": [{"properties": {"strokeWidth": lit(3)}}]},
                      labels={qref(f): "Remise moyenne"}), None
    if vid in ("stock_collection", "manque_collection"):
        f = mes("Stock restant au coût" if vid == "stock_collection" else "Remises accordées")
        return graphe("clusteredBarChart", {"Category": [col("Produits", "collection")], "Y": [f]},
                      {"dataPoint": [{"properties": {"fill": color(BLEU)}}], "labels": [LABELS()], "categoryAxis": [AXE()],
                       "valueAxis": [AXE(False)], "legend": LEG()}, tri=(f, "Descending")), None
    if vid == "table_perte":
        cols = [col("Produits", "nom"), col("Produits", "collection"), mes("Pièces vendues sous le coût"), mes("Marge perdue sous le coût")]
        objs = dict(TABLE_STYLE)
        objs["total"] = [{"properties": {"totals": lit(False)}}]
        return graphe("tableEx", {"Values": cols}, objs,
                      labels={"Produits.nom": "Produit", "Produits.collection": "Collection",
                              f"{M}.Pièces vendues sous le coût": "Pièces sous le coût", f"{M}.Marge perdue sous le coût": "Marge perdue"},
                      tri=(mes("Marge perdue sous le coût"), "Descending")), None
    # --- page 6 (gains)
    if vid == "gains_leviers":
        a, b = mes("Gain courbe de tailles"), mes("Gain production au plus juste")
        return graphe("clusteredColumnChart", {"Y": [a, b]},
                      {"dataPoint": [serie_mesure(a, BLEU), serie_mesure(b, GRIS_CLAIR)], "labels": [LABELS()],
                       "categoryAxis": [AXE(False)], "valueAxis": [AXE(False)], "legend": LEG(True)},
                      labels={qref(a): "Courbe de tailles", qref(b): "Production au plus juste"}), None
    raise KeyError(vid)


def theme() -> dict:
    return {
        "name": "Blue Wall - étude indépendante",
        "dataColors": [BLEU, GRIS_CLAIR, GRIS_BARRE, "#FFFFFF", "#3A3B41", "#C8C8CC", "#7AA2F0", "#101E35"],
        "background": "#000000", "foreground": "#FFFFFF", "tableAccent": BLEU, "good": BLEU, "neutral": GRIS_CLAIR, "bad": GRIS_CLAIR,
        "textClasses": {"callout": {"fontFace": "Segoe UI Semibold", "fontSize": 26, "color": "#FFFFFF"},
                        "title": {"fontFace": "Segoe UI Semibold", "fontSize": 12, "color": "#FFFFFF"},
                        "header": {"fontFace": "Segoe UI Semibold", "fontSize": 11, "color": "#FFFFFF"},
                        "label": {"fontFace": "Segoe UI", "fontSize": 11, "color": GRIS_TXT}},
        "visualStyles": {
            "page": {"*": {"outspace": [{"color": {"solid": {"color": "#000000"}}}]}},
            "*": {"*": {"background": [{"show": False, "transparency": 100}], "border": [{"show": False}],
                        "title": [{"show": False}], "visualHeader": [{"show": False}], "dropShadow": [{"show": False}],
                        "categoryAxis": [{"labelColor": {"solid": {"color": GRIS_TXT}}, "showAxisTitle": False, "gridlineShow": False}],
                        "valueAxis": [{"labelColor": {"solid": {"color": GRIS_TXT}}, "showAxisTitle": False,
                                       "gridlineColor": {"solid": {"color": "#2E2F35"}}}],
                        "legend": [{"labelColor": {"solid": {"color": GRIS_TXT}}}],
                        "labels": [{"color": {"solid": {"color": "#FFFFFF"}}}]}}}}


def ecrire_rapport(page_active: int):
    if RP.exists():
        shutil.rmtree(RP)
    d, res = RP / "definition", RP / "StaticResources"
    ecrire(RP / "definition.pbir", json.dumps({"version": "4.0", "datasetReference": {"byPath": {"path": f"../{NOM}.SemanticModel"}}}, indent=2))
    ecrire(RP / ".platform", json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Report", "displayName": NOM}, "config": {"version": "2.0", "logicalId": str(uuid.uuid4())}}, indent=2))
    ecrire(d / "version.json", json.dumps({"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
                                           "version": "2.0.0"}, indent=2))
    (res / "SharedResources" / "BaseThemes").mkdir(parents=True, exist_ok=True)
    shutil.copy(BASE_THEME, res / "SharedResources" / "BaseThemes" / BASE_THEME.name)
    reg = res / "RegisteredResources"
    reg.mkdir(parents=True, exist_ok=True)
    th = json.dumps(theme(), indent=2, ensure_ascii=False)
    (reg / "BlueWall_Theme.json").write_text(th, encoding="utf-8")
    (PBI / "theme_blue_wall.json").write_text(th, encoding="utf-8")

    pages = [fn() for fn in PAGES.values()]
    items = [{"name": "BlueWall_Theme.json", "path": "BlueWall_Theme.json", "type": "CustomTheme"}]
    for p in pages:
        img = f"fond_page_{p.numero:02d}.png"
        ds.dessiner_page(p).save(reg / img, optimize=True)
        items.append({"name": img, "path": img, "type": "Image"})
    version = {"visual": "2.14.0", "report": "3.4.0", "page": "2.3.1"}
    ecrire(d / "report.json", json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.3.0/schema.json",
        "themeCollection": {"baseTheme": {"name": BASE_THEME.stem, "reportVersionAtImport": version, "type": "SharedResources"},
                            "customTheme": {"name": "BlueWall_Theme.json", "reportVersionAtImport": version, "type": "RegisteredResources"}},
        "objects": {"section": [{"properties": {"verticalAlignment": lit("Top")}}]},
        "resourcePackages": [{"name": "SharedResources", "type": "SharedResources",
                              "items": [{"name": BASE_THEME.stem, "path": f"BaseThemes/{BASE_THEME.name}", "type": "BaseTheme"}]},
                             {"name": "RegisteredResources", "type": "RegisteredResources", "items": items}],
        "settings": {"useStylableVisualContainerHeader": True, "exportDataMode": "AllowSummarized", "defaultDrillFilterOtherVisuals": True,
                     "allowChangeFilterTypes": True, "useEnhancedTooltips": True, "useDefaultAggregateDisplayName": True}},
        indent=2, ensure_ascii=False))

    ordre = []
    for p in pages:
        pid = f"page{p.numero:02d}{uuid.uuid5(uuid.NAMESPACE_URL, NOM + str(p.numero)).hex[:14]}"
        ordre.append(pid)
        img = f"fond_page_{p.numero:02d}.png"
        ecrire(d / "pages" / pid / "page.json", json.dumps({
            "$schema": PAGE_SCHEMA, "name": pid, "displayName": p.nom_onglet, "displayOption": "FitToPage", "height": 1080, "width": 1920,
            "objects": {"background": [{"properties": {"image": {"image": {
                "name": lit(img), "url": {"expr": {"ResourcePackageItem": {"PackageName": "RegisteredResources", "PackageType": 1, "ItemName": img}}},
                "scaling": lit("Fit")}}, "transparency": lit(0)}}],
                "outspace": [{"properties": {"color": color("#000000")}}]}}, indent=2, ensure_ascii=False))
        r = Rapport()
        for c in p.cartes:
            if c.style == "filtres":
                for fid, zone in c.zones_filtres():
                    v, f = visuel(fid)
                    r.ajouter(fid, zone, v, f)
            elif c.style == "texte":
                r.ajouter(c.visuel, c.zone_visuel, zone_texte(p.textes[c.visuel]))
            elif c.visuel:
                v, f = visuel(c.visuel)
                r.ajouter(c.visuel, c.zone_visuel, v, f)
        for vc in r.visuels:
            ecrire(d / "pages" / pid / "visuals" / vc["name"] / "visual.json", json.dumps(vc, indent=2, ensure_ascii=False))
    ecrire(d / "pages" / "pages.json", json.dumps({"$schema": PAGES_SCHEMA, "pageOrder": ordre, "activePageName": ordre[page_active]}, indent=2))


def ecrire_pbip():
    ecrire(PBI / f"{NOM}.pbip", json.dumps({"version": "1.0", "artifacts": [{"report": {"path": f"{NOM}.Report"}}],
                                            "settings": {"enableAutoRecovery": True}}, indent=2))
    ecrire(PBI / ".gitignore", "**/.pbi/localSettings.json\n**/.pbi/cache.abf\n")


if __name__ == "__main__":
    page = int(sys.argv[sys.argv.index("--page") + 1]) if "--page" in sys.argv else 0
    ecrire_modele()
    ecrire_rapport(page)
    ecrire_pbip()
    print("Projet écrit :", PBI / f"{NOM}.pbip")
