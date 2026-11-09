"""Construit notebooks/analyse.ipynb (cellules en français), à exécuter ensuite avec nbconvert."""
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
cells = []


def md(s):
    cells.append(nbf.v4.new_markdown_cell(s.strip()))


def code(s):
    cells.append(nbf.v4.new_code_cell(s.strip()))


md("""
# La data derrière la Blue Wall : analyses
*Étude indépendante, non affiliée à la Karmine Corp.*

Chaque section répond à la question d'une page du rapport.
- **RÉEL** : catalogue de la boutique, résultats sportifs, audience, streams de Kameto (voir `data/SOURCES.md`).
- **SIMULÉ** : ventes, clients, billetterie, test A/B. Ces données sont produites par `src/generate_sim.py` avec une graine fixe. **Ce ne sont pas des données de la KC.**
- **ESTIMATION** : les gains chiffrés, avec leurs hypothèses écrites noir sur blanc.

Les tables agrégées viennent des requêtes SQL (`sql/`, lancées par `src/run_sql.py`).
""")

code("""
from pathlib import Path
import numpy as np, pandas as pd, matplotlib.pyplot as plt
from scipy import stats
import statsmodels.formula.api as smf
from statsmodels.stats.proportion import proportions_ztest, proportion_effectsize
from statsmodels.stats.power import NormalIndPower

ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
CLEAN, OUTD = ROOT / "data" / "clean", ROOT / "data" / "output"
BLEU, ROUGE, GRIS, NUIT = "#2F6BD6", "#C93636", "#A3A3A3", "#101E35"
plt.rcParams.update({"figure.dpi": 110, "axes.spines.top": False, "axes.spines.right": False,
                     "font.size": 10})
rng = np.random.default_rng(7)
FIN = pd.Timestamp("2026-11-08")
MOIS_PERIODE = 22.25            # 01/01/2025 -> 08/11/2026, pour annualiser
lire = lambda n: pd.read_csv(OUTD / f"{n}.csv")

produits = pd.read_csv(CLEAN / "sim_produits.csv", parse_dates=["date_lancement"])
commandes = pd.read_csv(CLEAN / "sim_commandes.csv", parse_dates=["date_commande"])
lignes = pd.read_csv(CLEAN / "sim_lignes.csv")
stock = pd.read_csv(CLEAN / "sim_stock.csv", parse_dates=["date_rupture"])
L = (lignes.merge(commandes[["order_id", "date_commande", "client_id"]], on="order_id")
           .merge(produits[["product_id", "nom", "famille", "collection", "date_lancement",
                            "prix_plein_ttc", "cout_unitaire_ht", "precommande"]], on="product_id"))
L["jour"] = (L.date_commande - L.date_lancement).dt.days
gains = []   # tableau final de la page 6
print(f"{len(commandes):,} commandes simulées, {L.montant_ht.sum()/1e6:.2f} M€ HT sur la période")
""")

# ---------------------------------------------------------------- Page 1
md("""
## Page 1 · Audience et sponsors (RÉEL, plus une ESTIMATION)
**Question :** combien vaut l'audience de la KC pour un partenaire ?
""")
code("""
aud = pd.read_csv(CLEAN / "audience_2026.csv")
eq = aud[aud.mesure.str.startswith("audience moyenne") & (aud.evenement == "LEC Versus 2026")].copy()
eq["equipe"] = eq.mesure.str.replace("audience moyenne ", "", regex=False)
eq = eq.sort_values("valeur")
fig, ax = plt.subplots(figsize=(6, 2.6))
ax.barh(eq.equipe, eq.valeur / 1000, color=[ROUGE if e == "Karmine Corp" else GRIS for e in eq.equipe])
ax.set_xlabel("Audience moyenne (milliers)"); ax.set_title("LEC Versus 2026 : audience moyenne par équipe (Esports Charts)")
plt.tight_layout(); plt.show()
spring = aud[aud.evenement == "LEC Spring 2026"].set_index("mesure").valeur
part_co = spring[spring.index.str.contains("co-streams")].iloc[0]
print(f"Part de l'audience du LEC Spring 2026 passée par les co-streams : {part_co:.0%}")
""")
code("""
kam = pd.read_csv(CLEAN / "kameto_twitch.csv")
g = kam.groupby("match_kc_ce_jour").spectateurs_moyens.agg(["mean", "count"])
ratio = g.loc[1, "mean"] / g.loc[0, "mean"]
print(g.rename(index={0: "sans match KC", 1: "avec match KC"}).round(0))
print(f"Les jours de match de la KC, Kameto fait {ratio:.1f} fois plus de spectateurs moyens "
      f"(petit échantillon : {int(g['count'].sum())} streams, à présenter comme une indication).")

res = pd.read_csv(CLEAN / "kameto_twitch_resume_365j.csv").set_index("mesure").valeur
heures = res["heures regardées"]
# ESTIMATION : 1 heure regardée = 1 impression d'un logo partenaire à l'écran ; CPM de 5 à 10 €
valeur_bas, valeur_haut = heures * 5 / 1000, heures * 10 / 1000
print(f"Heures regardées chez Kameto sur 365 jours : {heures/1e6:.1f} M")
print(f"Valeur média d'un logo sur ce seul canal : {valeur_bas/1e3:,.0f} à {valeur_haut/1e3:,.0f} k€ par an (ESTIMATION)")
""")
code("""
# Gain : un rapport d'audience propre aide à revaloriser les contrats renouvelés.
SPONSORING_PUBLIE = 2_300_000        # Sheep Esports, 2024 (année 2023)
gains.append(dict(levier="Sponsors : rapport d'audience pour les renouvellements",
                  gain_bas=SPONSORING_PUBLIE * .03, gain_haut=SPONSORING_PUBLIE * .08,
                  hypothese="+3 % à +8 % sur ~2,3 M€ de sponsoring annuel (chiffre publié pour 2023)",
                  nature="chiffre d'affaires"))
print(gains[-1])
""")

# ---------------------------------------------------------------- Page 2
md("""
## Page 2 · Boutique : stock, tailles et démarques (RÉEL, plus SIMULÉ)
**Question :** comment vendre plus au prix plein et solder moins ?
""")
code("""
coll = lire("01_ventes_par_collection")
cols = ["collection", "ca_ht", "taux_marge", "part_unites_prix_plein", "part_j0_j3_sur_4_semaines",
        "taux_ecoulement", "valeur_stock_final_ht"]
coll[cols].head(12)
""")
code("""
cb = lire("02_courbe_lancement")
fig, ax = plt.subplots(figsize=(6.5, 3))
for c, d in cb.groupby("collection"):
    ax.plot(d.jour, d.part_cumulee_8_semaines, color=BLEU, alpha=.35)
moy = cb.groupby("jour").part_cumulee_8_semaines.mean()
ax.plot(moy.index, moy.values, color=ROUGE, lw=2.5, label="moyenne des collections")
ax.axvline(3, color=GRIS, ls="--"); ax.set_xlabel("Jours depuis le lancement")
ax.set_ylabel("Part des ventes des 8 semaines"); ax.legend(frameon=False)
ax.set_title("Un drop se joue sur ses premiers jours (SIMULÉ)")
plt.tight_layout(); plt.show()
print(f"En moyenne, {moy.loc[3]:.0%} des ventes des 8 premières semaines sont faites entre J0 et J3.")
""")
md("""
### Prévoir la demande d'un drop à partir de ses 4 premiers jours
Modèle log-log au niveau du produit : `log(ventes J0-J55) = a + b·log(ventes J0-J3) + groupe` (maillot, textile ou autre).
- Entraînement sur les produits lancés en **2025**, test sur ceux lancés en **2026** (données mises de côté).
- Référence naïve : ventes J0-J3 multipliées par le ratio médian observé en 2025.
- Les produits tombés en rupture avant J55 sont exclus : leurs ventes ne reflètent plus la demande.
""")
code("""
elig = produits[(produits.date_lancement >= "2025-01-01") & (produits.date_lancement + pd.Timedelta(days=55) <= FIN)
                & (produits.famille != "service") & (produits.precommande == 0)].copy()
rupt = (stock.merge(produits[["product_id", "date_lancement"]], on="product_id")
             .assign(r=lambda d: (d.date_rupture - d.date_lancement).dt.days < 55)
             .groupby("product_id").r.mean())
elig = elig[elig.product_id.map(rupt).fillna(0) < .5]
v = L[L.product_id.isin(elig.product_id)]
agg = pd.DataFrame({"j0_3": v[v.jour.between(0, 3)].groupby("product_id").quantite.sum(),
                    "j0_55": v[v.jour.between(0, 55)].groupby("product_id").quantite.sum()}).fillna(0)
d = elig.set_index("product_id")[["nom", "famille", "date_lancement"]].join(agg).dropna()
d = d[(d.j0_3 > 0) & (d.j0_55 > 0)]
d["test"] = d.date_lancement >= "2026-01-01"
d["groupe"] = np.where(d.famille.isin(["maillot", "textile"]), d.famille, "autre")   # cartes, accessoires...
train, test = d[~d.test], d[d.test]
m = smf.ols("np.log(j0_55) ~ np.log(j0_3) + C(groupe)", data=train).fit()
k = (train.j0_55 / train.j0_3).median()
k_groupe = (train.j0_55 / train.j0_3).groupby(train.groupe).median()
test = test.assign(prev_regression=np.exp(m.predict(test)) * np.exp(m.mse_resid / 2),
                   prev_ratio=test.j0_3 * k,
                   prev_ratio_groupe=test.j0_3 * test.groupe.map(k_groupe))
wape = lambda y, p: np.abs(y - p).sum() / y.sum()
scores = pd.Series({"Régression log-log": wape(test.j0_55, test.prev_regression),
                    f"Ratio unique (x{k:.1f})": wape(test.j0_55, test.prev_ratio),
                    "Ratio par groupe": wape(test.j0_55, test.prev_ratio_groupe)}).sort_values()
print(f"{len(train)} produits d'entraînement (2025), {len(test)} de test (2026)")
print("Ratios par groupe (ventes J0-J55 / ventes J0-J3) :", k_groupe.round(2).to_dict())
print("Erreur (WAPE) sur les produits 2026, mis de côté :"); print(scores.map("{:.1%}".format).to_string())
print(f"Méthode retenue : {scores.index[0]} (la plus simple qui valide le mieux)")
test[["nom", "groupe", "j0_3", "j0_55", "prev_regression", "prev_ratio", "prev_ratio_groupe"]].round(0).to_csv(OUTD / "nb_prevision_drops.csv")
scores.rename("wape").to_csv(OUTD / "nb_prevision_scores.csv")
""")
md("""
### Courbe de tailles : ce qu'on commande face à ce qu'on vend
Les ruptures RÉELLES par taille (relevé de la boutique) et la simulation racontent la même chose : on manque de XXL et de 3XL, et il reste des XS.
""")
code("""
t = lire("03_tailles").set_index("taille").loc[["XS", "S", "M", "L", "XL", "XXL", "3XL"]]
fig, axes = plt.subplots(1, 2, figsize=(9, 2.8))
x = np.arange(len(t))
axes[0].bar(x - .2, t.part_production, .4, color=GRIS, label="production")
axes[0].bar(x + .2, t.part_demande, .4, color=BLEU, label="demande")
axes[0].set_xticks(x, t.index); axes[0].legend(frameon=False); axes[0].set_title("Part de chaque taille (SIMULÉ)")
axes[1].bar(x, t.part_variantes_epuisees_reel, color=ROUGE)
axes[1].set_xticks(x, t.index); axes[1].set_title("Variantes épuisées le 09/11/2026 (RÉEL)")
plt.tight_layout(); plt.show()

# Même production totale, répartie selon la demande : combien de ventes en plus, combien de stock en moins ?
t["demande"] = t.vendues + t.ventes_perdues_verite
t["prod_ideale"] = t.production.sum() * t.part_demande / t.part_demande.sum()
t["vendues_ideal"] = np.minimum(t.demande, t.prod_ideale)
ventes_en_plus = t.vendues_ideal.sum() - t.vendues.sum()
pp = L[(L.famille.isin(["maillot", "textile"])) & (L.remise_pct == 0)]
marge_piece = pp.marge_ht.sum() / pp.quantite.sum()
an = 12 / MOIS_PERIODE
print(f"Ventes récupérées avec la bonne courbe de tailles : {ventes_en_plus:,.0f} pièces sur la période")
print(f"Marge moyenne d'une pièce vendue au prix plein : {marge_piece:.1f} € HT")
gains.append(dict(levier="Stock : courbe de tailles calée sur la demande",
                  gain_bas=.5 * ventes_en_plus * marge_piece * an, gain_haut=ventes_en_plus * marge_piece * an,
                  hypothese="50 à 100 % des ventes perdues par taille récupérées, à la marge du prix plein",
                  nature="marge"))
t[["production", "vendues", "ventes_perdues_verite", "part_production", "part_demande", "prod_ideale",
   "part_variantes_epuisees_reel"]].round(3).to_csv(OUTD / "nb_tailles.csv")
print(gains[-1])
""")
md("""
### Ce que coûtent les remises
""")
code("""
rm = lire("04_remises_marge")
tab = rm.groupby("tranche_remise")[["unites", "ca_ht", "marge_ht"]].sum()
tab["taux_marge"] = tab.marge_ht / tab.ca_ht
tab["marge_par_piece"] = tab.marge_ht / tab.unites
print(tab.round(2))

# Production évitable = pièces soldées à 50 % ou plus + stock restant au 08/11/2026
liquid = L[(L.remise_pct >= .5) & (L.famille.isin(["maillot", "textile"]))]
stk = stock.merge(produits[["product_id", "famille", "cout_unitaire_ht", "prix_plein_ttc"]], on="product_id")
stk = stk[stk.famille.isin(["maillot", "textile"]) & (stk.fabrique_a_la_commande == 0)]
surplus_unites = liquid.quantite.sum() + stk.stock_final.sum()
cout_moyen = (stk.stock_initial * stk.cout_unitaire_ht).sum() / stk.stock_initial.sum()
# Une pièce non produite économise son coût ; si elle aurait été soldée, on perd son prix de solde :
# économie nette = coût - prix de solde HT. Une pièce restée en stock fait perdre tout son coût.
prix_solde_ht = liquid.montant_ht.sum() / liquid.quantite.sum()
print(f"Surplus sur la période : {surplus_unites:,.0f} pièces (soldées à -50 % ou plus, ou encore en stock)")
print(f"Coût moyen d'une pièce : {cout_moyen:.1f} € HT ; prix moyen en solde profonde : {prix_solde_ht:.1f} € HT")
n_liq, n_stk = liquid.quantite.sum(), stk.stock_final.sum()
gain_par_piece_evitee = (n_liq * (cout_moyen - prix_solde_ht).clip(min=0) + n_stk * cout_moyen) / surplus_unites
gains.append(dict(levier="Stock : produire au plus juste chaque drop (moins de soldes et d'invendus)",
                  gain_bas=.10 * surplus_unites * gain_par_piece_evitee * an,
                  gain_haut=.25 * surplus_unites * gain_par_piece_evitee * an,
                  hypothese="10 à 25 % du surplus évité grâce à la prévision J0-J3 ; gain = coût non engagé net du prix de solde",
                  nature="marge"))
print(gains[-1])
""")

# ---------------------------------------------------------------- Page 3
md("""
## Page 3 · Fans : RFM, réachat et LTV (SIMULÉ)
**Question :** qui rachète, et quand faut-il relancer ?
""")
code("""
rfm = lire("05_rfm")
seg = rfm.groupby("segment").agg(clients=("client_id", "count"), ca_ht=("montant_ht", "sum"),
                                 frequence=("frequence", "mean"), recence=("recence_jours", "median"))
seg["part_clients"] = seg.clients / seg.clients.sum(); seg["part_ca"] = seg.ca_ht / seg.ca_ht.sum()
seg.round(3)
""")
code("""
ltv = lire("06_ltv_cohortes")
ltv["cohorte"] = pd.to_datetime(ltv.cohorte)
ltv["trimestre"] = ltv.cohorte.dt.to_period("Q").astype(str)
fig, ax = plt.subplots(figsize=(6.5, 3))
for q, dq in ltv.groupby("trimestre"):
    w = dq.groupby("mois_depuis_premier_achat").apply(lambda x: np.average(x.ca_cumule_par_client_ht, weights=x.clients))
    ax.plot(w.index, w.values, label=q)
ax.set_xlabel("Mois depuis le premier achat"); ax.set_ylabel("CA HT cumulé par client (€)")
ax.legend(frameon=False, ncol=2, fontsize=8); ax.set_title("LTV par trimestre de premier achat (SIMULÉ, sans biais de censure)")
plt.tight_layout(); plt.show()
l12 = ltv[ltv.mois_depuis_premier_achat == 12]
print(f"LTV à 12 mois (moyenne pondérée des cohortes observées 12 mois) : {np.average(l12.ca_cumule_par_client_ht, weights=l12.clients):.0f} € HT")
rea = lire("07_reachat"); rea
""")
code("""
# Gain CRM : relancer les segments « À relancer » et « Fidèles à réactiver » avant chaque drop
cibles = seg.loc[["6. À relancer", "3. Fidèles à réactiver"], "clients"].sum()
panier_ht = commandes.montant_net_ht.mean()
taux_marge = L.marge_ht.sum() / L.montant_ht.sum()
N_CAMPAGNES = 4                                   # un envoi ciblé par grand drop
for nom, up in [("bas", .01), ("haut", .03)]:
    print(f"{nom} : +{up:.0%} de réachat incrémental x {cibles:,} clients x {panier_ht:.0f} € x {N_CAMPAGNES} campagnes")
gains.append(dict(levier="CRM : relancer les bons segments avant un drop et après un match",
                  gain_bas=cibles * .01 * panier_ht * taux_marge * N_CAMPAGNES,
                  gain_haut=cibles * .03 * panier_ht * taux_marge * N_CAMPAGNES,
                  hypothese=f"+1 à +3 points de réachat incrémental sur {cibles:,} clients ciblés, 4 campagnes par an, marge {taux_marge:.0%}",
                  nature="marge"))
print(gains[-1])
""")

# ---------------------------------------------------------------- Page 4
md("""
## Page 4 · Événements et Arènes (RÉEL pour les dates et capacités, SIMULÉ pour les ventes)
**Question :** comment remplir plus de dates, et mieux ?
""")
code("""
ev = lire("09_billetterie"); ev["date_evenement"] = pd.to_datetime(ev.date_evenement)
billets = pd.read_csv(CLEAN / "sim_billets.csv")
evs = pd.read_csv(CLEAN / "sim_evenements.csv", parse_dates=["date_evenement"])
cum = (billets.groupby(["event_id", "jours_avant_evenement"]).billets.sum().groupby(level=0).cumsum()
              .reset_index().merge(evs[["event_id", "capacite", "lieu"]], on="event_id"))
fig, ax = plt.subplots(figsize=(6.5, 3))
for e, de in cum.groupby("event_id"):
    de = de.sort_values("jours_avant_evenement", ascending=False)
    ax.plot(-de.jours_avant_evenement, de.billets / de.capacite, color=BLEU if "Arènes" in de.lieu.iat[0] else ROUGE, alpha=.6)
ax.set_xlabel("Jours avant l'événement"); ax.set_ylabel("Taux de remplissage")
ax.set_title("Courbes de remplissage : Arènes en bleu, grandes salles en rouge (SIMULÉ)")
plt.tight_layout(); plt.show()
""")
md("""
### Prévoir le remplissage final à partir des 48 premières heures
Modèle simple : `remplissage final = min(1 ; k × part vendue en 48 h)`. `k` est estimé sur les événements 2024-2025 qui n'ont **pas** été complets (pour eux, la demande totale est connue). Le modèle est testé sur les événements 2026.
""")
code("""
ok = ev[ev.reporte_rembourse == 0]
train = ok[(ok.date_evenement < "2026-01-01") & (ok.taux_remplissage < 1)]
k = (train.taux_remplissage / train.part_capacite_vendue_48h).median()
test = ok[ok.date_evenement >= "2026-01-01"].copy()
test["prevision"] = np.minimum(1, k * test.part_capacite_vendue_48h)
test["erreur_points"] = (test.prevision - test.taux_remplissage) * 100
print(f"k = {k:.2f} (estimé sur {len(train)} événements non complets)")
print(test[["nom", "part_capacite_vendue_48h", "taux_remplissage", "prevision", "erreur_points"]].round(3).to_string(index=False))
nc = test[test.taux_remplissage < 1]
print(f"Erreur absolue moyenne sur les {len(nc)} événements 2026 non complets : {nc.erreur_points.abs().mean():.1f} points "
      f"(les événements complets sont trivialement bien prévus)")
test.to_csv(OUTD / "nb_billetterie_prevision.csv", index=False)
""")
code("""
# Demande non servie : les listes d'attente des événements complets
complets = ok[ok.taux_remplissage >= 1]
prix_moyen = (billets.ca_ttc.sum() / billets.billets.sum())
print(f"{len(complets)} événements complets ; liste d'attente moyenne : {complets.liste_attente.mean():.0f} personnes")
ca_date = 3000 * billets.merge(evs[["event_id", "lieu"]]).query("lieu == 'Les Arènes, Évry'").pipe(lambda b: b.ca_ttc.sum() / b.billets.sum())
print(f"Une date de plus aux Arènes complète : ~{ca_date/1e3:.0f} k€ TTC de billetterie (SIMULÉ)")
print("Repère publié : ~1,5 M€/an pour ~20 événements en pleine exploitation (Sheep Esports, 2024), soit ~75 k€ par événement.")
gains.append(dict(levier="Billetterie : chiffrer la demande non servie pour obtenir plus de dates",
                  gain_bas=1 * ca_date / 1.055, gain_haut=3 * ca_date / 1.055,
                  hypothese="1 à 3 dates de plus par an aux Arènes (3 000 places), au prix moyen simulé, TVA billetterie 5,5 % ; dépend du calendrier Riot",
                  nature="chiffre d'affaires HT"))
print(gains[-1])
""")

# ---------------------------------------------------------------- Page 5
md("""
## Page 5 · Les résultats font-ils vendre ? (résultats RÉELS, ventes SIMULÉES)
**1. Vue descriptive.** Pour chaque moment sportif, le CA du jour est rapporté à la médiane des jours J-24 à J-4 (hors promotions). Attention : les matchs de playoffs se suivent à quelques jours d'écart, donc les effets se chevauchent.

**2. Mesure.** On fait une régression sur les ventes jour par jour :
- `log(CA du jour)` ~ jour de la semaine + mois (qui absorbe les soldes de mars-avril 2026) + Black Friday + lancements + un indicateur par type de moment (fenêtre J0-J3) ;
- comme chaque type de moment est une variable à part, les chevauchements sont démêlés ;
- les erreurs standard sont robustes à l'autocorrélation (Newey-West, 7 jours).
""")
code("""
es = lire("08_effet_resultats")
prof = es.groupby(["type_moment", "jour_relatif"]).indice_ca.mean().unstack(0)
fig, ax = plt.subplots(figsize=(6.5, 3))
for c, col in zip(["Qualification", "Finale", "Victoire", "Défaite"], [ROUGE, NUIT, BLEU, GRIS]):
    if c in prof:
        ax.plot(prof.index, prof[c], marker="o", ms=3, color=col, label=c)
ax.axhline(1, color=GRIS, lw=.8); ax.axvline(0, color=GRIS, ls="--", lw=.8)
ax.set_xlabel("Jours autour du moment sportif"); ax.set_ylabel("CA / référence")
ax.legend(frameon=False); ax.set_title("Ventes autour des moments sportifs, vue descriptive (SIMULÉ)")
plt.tight_layout(); plt.show()
prof.round(3).to_csv(OUTD / "nb_profil_moments.csv")
""")
code("""
jours = pd.date_range("2025-01-01", FIN)
df = pd.DataFrame(index=jours)
df["ca"] = L.groupby("date_commande").montant_ht.sum().reindex(jours, fill_value=0)
df["log_ca"] = np.log(df.ca + 1)
cal = lire("00_calendrier"); cal.index = pd.to_datetime(cal.date)
df["black_friday"], df["soldes"] = cal.black_friday, cal.soldes
df["dow"], df["mois"] = df.index.day_of_week, df.index.to_period("M").astype(str)
lanc = produits[produits.famille != "service"].groupby("collection").date_lancement.min()
lanc = lanc[lanc >= "2025-01-01"]
fenetre = lambda dates, a, b: pd.Series([any(a <= (d - x).days <= b for x in dates) for d in jours], index=jours).astype(int)
df["lancement_j0_3"], df["lancement_j4_10"] = fenetre(lanc, 0, 3), fenetre(lanc, 4, 10)
res = pd.read_csv(CLEAN / "kc_resultats_lol.csv", parse_dates=["date"])
res = res[~res.phase.str.startswith("Fin de saison")]
res["type"] = np.select([res.enjeu.fillna("").str.startswith("Qualifiée"), res.phase.eq("Finale"), res.resultat.eq("V")],
                        ["qualification", "finale", "victoire"], "defaite")
for typ, dt in res.groupby("type"):
    df[typ] = fenetre(dt.date, 0, 3)
reg = smf.ols("log_ca ~ C(dow) + C(mois) + black_friday + lancement_j0_3 + lancement_j4_10"
              " + qualification + finale + victoire + defaite", data=df).fit(cov_type="HAC", cov_kwds={"maxlags": 7})
noms = {"qualification": "Qualification", "finale": "Finale", "victoire": "Victoire", "defaite": "Défaite",
        "lancement_j0_3": "Lancement d'une collection (J0-J3)"}
ci = reg.conf_int()
effet = pd.DataFrame({"moment": [noms[k] for k in noms],
                      "nb_moments": [int(res.type.eq(k).sum()) if k in res.type.values else len(lanc) for k in noms],
                      "hausse_ca_j0_j3": [np.exp(reg.params[k]) - 1 for k in noms],
                      "ic95_bas": [np.exp(ci.loc[k, 0]) - 1 for k in noms],
                      "ic95_haut": [np.exp(ci.loc[k, 1]) - 1 for k in noms],
                      "p_value": [reg.pvalues[k] for k in noms]})
effet.round(3).to_csv(OUTD / "nb_effet_resultats.csv", index=False)
print(f"R² de la régression : {reg.rsquared:.2f} sur {len(df)} jours")
effet.round(3)
""")
md("""
### Test A/B (fictif) : guide des tailles sur la page du maillot
""")
code("""
ab = pd.read_csv(CLEAN / "sim_ab_test.csv")
s = ab.groupby("variante").agg(n=("session_id", "count"), conv=("a_converti", "sum"), ca=("ca_ttc", "sum"))
z, p = proportions_ztest(s.conv.values[::-1], s.n.values[::-1])        # B contre A
cr = s.conv / s.n
lift = cr["B"] / cr["A"] - 1
# taille d'échantillon nécessaire pour détecter +10 % relatif à partir du taux de A
es_h = proportion_effectsize(cr["A"] * 1.10, cr["A"])
n_req = NormalIndPower().solve_power(effect_size=es_h, alpha=.05, power=.8, alternative="two-sided")
# bootstrap du CA par session
a = ab.loc[ab.variante == "A", "ca_ttc"].values; b = ab.loc[ab.variante == "B", "ca_ttc"].values
bd = np.array([rng.choice(b, len(b)).mean() - rng.choice(a, len(a)).mean() for _ in range(2000)])
print(f"Conversion A {cr['A']:.2%} | B {cr['B']:.2%} | hausse relative {lift:+.1%} | p = {p:.4f}")
print(f"Sessions nécessaires pour détecter +10 % (alpha 5 %, puissance 80 %) : {n_req:,.0f} par variante ; observées : {s.n.min():,}")
sem = n_req / (s.n.mean() / 4)
print(f"Le test est significatif, mais il était sous-dimensionné : il aurait fallu environ {sem:.1f} semaines au lieu de 4. "
      "La taille d'échantillon se fixe AVANT de lancer le test.")
print(f"CA par session : +{bd.mean():.2f} € TTC (IC 95 % : {np.percentile(bd, 2.5):.2f} à {np.percentile(bd, 97.5):.2f})")
pd.DataFrame([dict(conv_A=cr["A"], conv_B=cr["B"], hausse_relative=lift, p_value=p, n_requis_par_variante=n_req,
                   n_observe_par_variante=s.n.min(), gain_ca_session=bd.mean(),
                   ic_bas=np.percentile(bd, 2.5), ic_haut=np.percentile(bd, 97.5))]).to_csv(OUTD / "nb_ab_test.csv", index=False)
""")

# ---------------------------------------------------------------- Page 6
md("""
## Page 6 · Ce que rapporterait un data analyst (ESTIMATION)
Chaque ligne reprend un calcul ci-dessus, avec son hypothèse. Les montants sont annuels.
""")
code("""
g = pd.DataFrame(gains)
g["gain_bas"] = g.gain_bas.round(-3); g["gain_haut"] = g.gain_haut.round(-3)
g.to_csv(OUTD / "gains_estimes.csv", index=False)
print(g[["levier", "gain_bas", "gain_haut", "nature"]].to_string(index=False))
print(f"\\nTOTAL : {g.gain_bas.sum()/1e3:,.0f} k€ à {g.gain_haut.sum()/1e3:,.0f} k€ par an")
print("Repère : un data analyst junior à Paris coûte environ 55 à 65 k€ par an, charges comprises (hypothèse).")
""")

nb = nbf.v4.new_notebook()
nb["cells"] = cells
nb["metadata"]["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
(ROOT / "notebooks").mkdir(exist_ok=True)
nbf.write(nb, ROOT / "notebooks" / "analyse.ipynb")
print("notebooks/analyse.ipynb écrit")
