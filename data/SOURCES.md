# Sources des données

Étude indépendante, non affiliée à la Karmine Corp. Relevés effectués du 8 au 9 novembre 2026, sauf mention contraire.

## Niveaux de vérification
- **source_primaire** : le chiffre a été lu directement chez l'émetteur (boutique KC, page Wikipedia du tournoi, communiqué officiel, SullyGnome).
- **source_secondaire** : le chiffre vient d'Esports Charts, mais il a été lu dans un article de Sheep Esports qui le cite. Esports Charts bloque les accès automatisés (Cloudflare), donc les pages n'ont pas pu être consultées directement.
- **a_verifier** : le chiffre n'est connu que par un extrait de moteur de recherche ou par un site peu fiable. Il doit être confirmé à la main avant d'être affiché dans le rapport.

---

## Données réelles

### `raw/boutique/` : catalogue public de la boutique (RÉEL)
- Fichiers :
  - `products_AAAA-MM-JJ.json` : le JSON brut du jour ;
  - `variants_snapshots.csv` : une ligne par variante et par jour.
- Source : endpoint public Shopify https://www.karminecorp.fr/products.json
- Collecte : `src/snapshot_boutique.py`, lancé chaque jour par la tâche planifiée Windows `KC_releve_boutique`, un relevé par jour depuis le 9 novembre 2026.
- Contenu : prix, prix barré (`compare_at_price`), remise, disponibilité par variante (taille), mention de précommande dans le titre.
- **Limites** :
  - Shopify indique seulement si une variante est disponible, pas la quantité en stock ;
  - une variante « épuisée » peut aussi n'avoir jamais été produite ;
  - aucune donnée de vente n'est publique.

### `raw/wayback/` : historique du catalogue, janvier 2025 à octobre 2026 (RÉEL)
- **Source :** les pages produit de karminecorp.fr archivées par la Wayback Machine (archive.org). La liste des captures vient de l'API CDX, et chaque page est lue dans sa version brute (`id_`).
- **Collecte :** `src/historique_wayback.py`, une requête par seconde, avec un cache local non versionné.
- **Contenu de chaque capture :** le prix, le prix barré, la remise, et la disponibilité de chaque taille. Ces informations viennent de l'objet produit Shopify inclus dans la page.
- **Filtre :** seuls les produits de marque Karmine sont gardés ; les produits partenaires (Logitech…) sont écartés.
- **Limite :** archive.org capture les pages au hasard des passages de ses robots. L'échantillon change d'un mois à l'autre, d'où des indicateurs en parts (part des pages soldées, part des tailles indisponibles), pas en volumes.

### `clean/kc_resultats_lol.csv` : résultats de la KC en LoL, 2025-2026 (RÉEL)
Les matchs de playoffs et internationaux, plus les classements de fin de saison régulière.

| Clé | Source |
|---|---|
| `wikipedia_lec_2025` | https://en.wikipedia.org/wiki/2025_LEC_season |
| `wikipedia_first_stand_2025` | https://en.wikipedia.org/wiki/2025_First_Stand_Tournament |
| `wikipedia_lec_2026` | https://en.wikipedia.org/wiki/2026_LEC_season |
| `wikipedia_msi_2026` | https://en.wikipedia.org/wiki/2026_Mid-Season_Invitational |
| `wikipedia_worlds_2026` | https://en.wikipedia.org/wiki/2026_League_of_Legends_World_Championship |
| `presse_ewc_2026` | GosuGamers : https://www.gosugamers.net/lol/news/78822-underdogs-rise-as-karmine-corp-and-dplus-reach-esports-world-cup-2026-league-of-legends-grand-final ; Inven Global : https://www.invenglobal.com/articles/23917/karmine-corp-shows-unyielding-tenacity-takes-down-t1 |
| `ewc_communique_2026` | https://esportsworldcup.com/en/press-releases/dplus-kia-win-lol-at-ewc26 (19/07/2026) |

Notes :
- Les phases de groupes de l'EWC et les matchs de saison régulière ne sont pas détaillés.
- Le tableau bas du LEC Versus a été reconstitué à partir du bracket de Wikipedia et vérifié pour la cohérence (chaque équipe éliminée une seule fois).
- Liquipedia et l'API de Leaguepedia ont refusé l'accès (403 et limite de requêtes) : à recouper si besoin.

### `clean/audience_2026.csv` : audience (SECONDAIRE ou À VÉRIFIER)

| Clé | Source |
|---|---|
| `sheep_lec_versus_equipes` | Sheep Esports, 10/03/2026 : https://www.sheepesports.com/en/articles/most-watched-teams-in-lec-versus-los-ratones-lead-ahead-of-g2-esports-and-karmine-corp/en |
| `sheep_lec_spring_2026` | Sheep Esports, juin 2026 : https://www.sheepesports.com/en/articles/official-lec-spring-split-2026-broadcasts-captured-just-30-of-total-audience-amid-year-on-year/en |
| `sheep_lec_summer_2026` | Sheep Esports, 22/09/2026 : https://www.sheepesports.com/en/articles/lec-summer-2026-continues-trend-of-declining-viewership-for-official-broadcasts/en |
| `sheep_x_spring_top_matchs` | Sheep Esports sur X : https://x.com/Sheep_Esports/status/2053474414394519724 (la date exacte du match, Roadtrip de Madrid du 8 au 10/05, est approximative) |
| `escharts_summer_2026` | https://escharts.com/news/lec-summer-2026-viewership (bloqué, chiffres lus dans un extrait de recherche) |
| `gurugamer_worlds_playin` | https://gurugamer.com/esports/worlds-2026-play-in-records-lowest-peak-viewership-since-2019-27466 |
| `recherche_ewc_finale` | résumé de recherche, source primaire non identifiée |
| `escharts_equipe_kc` | https://escharts.com/teams/lol/kameto (bloqué, chiffre lu dans un extrait de recherche) |

**À faire à la main** : ouvrir les pages Esports Charts dans un navigateur ordinaire pour confirmer les lignes `a_verifier` et relever, si possible :
- les heures regardées par équipe ;
- la part des co-streams pour les matchs de la KC.

Plusieurs extraits donnent des records différents pour la KC (1 332 274, 1 475 658 et 1 562 993) : ils datent de moments différents.

### `clean/kameto_twitch.csv` et `clean/kameto_twitch_resume_365j.csv` : streams de Kameto (RÉEL)
- Clé `sullygnome_kamet0_365j` : https://sullygnome.com/channel/kamet0/365, page lue le 08/11/2026. Heures en UTC.
- Seuls les 10 derniers streams visibles sur la page ont été relevés. Le site demande à ne pas être scrapé : aucune collecte automatisée n'a été faite.
- La colonne `match_kc_ce_jour` vient du recoupement avec `kc_resultats_lol.csv`.

### `clean/evenements_kc.csv` : KCX, Arènes, Roadtrips (RÉEL, presse)

| Clé | Source |
|---|---|
| `kc_x_kcx1` | https://twitter.com/KarmineCorp/status/1414692379869728775 |
| `presse_kcx_historique` | defense-92.fr : https://www.defense-92.fr/e-sport/kcx-4-la-karmine-corp-triomphe-dans-une-paris-la-defense-arena-en-ebullition-81616 et https://www.defense-92.fr/e-sport/le-kcx-revient-ce-samedi-a-la-paris-la-defense-arena-pour-un-quatrieme-round-81550 |
| `defense92_kcx4` | même source que ci-dessus |
| `grandparissud_cp_2024` | https://grandparissud.fr/app/uploads/2024/10/CP-4500-spectateurs-pour-la-premiere-de-la-Karmine-Corp-aux-Arenes.pdf |
| `esportsnet_arenes_2026` | esports.net, 06/05/2026 : https://www.esports.net/fr/actualites/karmine-corp-bilan-stade-arenes-evry/ |
| `sheep_kcx5_report` | Sheep Esports, 12/11/2025 : https://www.sheepesports.com/us/articles/karmine-corp-postpones-kcx5-to-2026/en |
| `kc_x_roadtrip_summer` | https://x.com/KarmineCorp/status/2054627731002790363 |

---

## Chiffres financiers de contexte (presse, non tabulés)
- Sheep Esports, 28/06/2024 : CA 2023 de 7,01 M€, merch ≈ 40 % du CA (≈ 2,5 M€), sponsoring ≈ 2,3 M€/an. https://www.sheepesports.com/fr/articles/karmine-corp-a-look-back-at-the-club-s-first-3-financial-years/fr
- Sheep Esports, 07/10/2026 : fin de la charge annuelle du slot LEC, renforts annoncés (dont le merch). https://www.sheepesports.com/en/articles/we-re-going-to-be-able-to-breathe-some-fresh-air-karmine-corp-can-finally-reinvest-after-years/en

## Données simulées (marquées « SIMULÉ » partout)
**Ce ne sont pas des données de la Karmine Corp.** Elles servent à démontrer les méthodes.
- Générateur : `src/generate_sim.py`, graine fixe 2026. Relancer le script redonne exactement les mêmes fichiers.
- Période : du 01/01/2025 au 08/11/2026.

### Ce qui est calé sur du réel
- **Le catalogue** : 115 produits réels, avec leurs prix pleins, leurs tailles et leur remise relevée le 09/11/2026. La remise simulée de chaque produit finit exactement à ce niveau réel. Deux maillots retirés du site (Pro 2025 et Pro 2026 Bleu) sont reconstitués, avec un prix en hypothèse (75 € et 80 €).
- **Les ruptures** : la production de chaque taille est calée sur la disponibilité réelle du 09/11/2026. Une taille épuisée en vrai a été sous-produite, une taille disponible a été produite en quantité suffisante. Résultat : 94 % de concordance entre les ruptures simulées et les ruptures réelles.
- **Le calendrier sportif réel 2025-2026** (`kc_resultats_lol.csv`) crée les pics de ventes.
- **Les ordres de grandeur publiés** :
  - CA merch 2025 calé à 4,0 M€ HT (2,5 M€ en 2023, objectif d'environ 4 M€ en 2024) ;
  - livraison offerte dès 120 € ;
  - Arènes de 3 000 places ;
  - affluence de l'inauguration des Arènes et du KCX 4.

### Principales hypothèses (toutes dans les constantes du générateur)
- **Demande** : courbe de tailles (L 26 %, M 23 %, XL 19 %, XXL 11 %, S 11 %, 3XL 6 %, XS 3 %) ; élasticité-prix de 1,2 (plafonnée à ×4) ; pic de lancement plus traîne ; saisonnalité (Noël, rentrée) ; effet des moments sportifs (qualification, finale, victoire).
- **Production** : courbe de tailles commandée trop centrée (trop de XS, pas assez de XXL et de 3XL). Plus la remise réelle d'un produit est forte, plus il a été sur-produit (hypothèse : une forte démarque signale un surstock).
- **Coûts de revient**, en part du prix plein HT : maillots 35 %, textile 38 %, accessoires 30 %, cartes 50 %.
- **Prix** : calés sur l'historique réel archivé : prix plein en 2025, soldes du 01/03 au 30/04/2026 (remise de 40 % au plus), Black Friday 2026 à partir du 02/11 (niveau réel relevé le 09/11).
- **Clients** : 45 000 clients ayant acheté avant 2025 ; part de clients qui reviennent d'environ 37 % ; sources d'acquisition et pays.
- **Billetterie** :
  - événements, dates et capacités réels quand ils sont connus (Arènes, KCX 4, KCX 5 reporté, Roadtrips 2025-2026) ;
  - 3 dates de 2025 hypothétiques ;
  - catégories et prix hypothétiques ;
  - capacité de l'Adidas Arena fixée à 7 500 (à vérifier).
- **Test A/B** : fictif. Page du maillot Worlds 2026, du 07/09 au 04/10/2026, conversion de 3,0 % (A) contre 3,4 % (B).

### Fichiers (`clean/sim_*.csv`)

| Fichier | Contenu |
|---|---|
| `sim_produits` / `sim_variantes` | Catalogue (réel et reconstitué), collection, date de lancement, coût |
| `sim_clients` | Clients (taille, pays, source d'acquisition, date du premier achat) |
| `sim_commandes` / `sim_lignes` | Commandes et lignes (prix plein, remise, prix payé, coût, marge) |
| `sim_stock` | Stock initial, ventes, stock final, date de rupture ; `demande_non_servie_verite` est la vérité du simulateur, inobservable en réalité |
| `sim_alertes_stock` | Alertes « retour en stock » (15 % des ventes perdues) : le signal observable |
| `sim_remises_jour` | Remise appliquée chaque jour à chaque produit |
| `sim_evenements` / `sim_billets` / `sim_liste_attente` | Billetterie jour par jour et listes d'attente |
| `sim_ab_test` | Sessions du test A/B fictif |

## Résultats des analyses (`output/`)
- `00_` à `12_*.csv` : sorties des requêtes SQL (`sql/`, lancées par `src/run_sql.py`).
- `nb_*.csv` et `gains_estimes.csv` : sorties du notebook `notebooks/analyse.ipynb`.

## Couche Power BI (`powerbi/`)
`src/prep_powerbi.py` assemble les données ci-dessus en un schéma en étoile, chargé par le rapport Power BI.

| Fichier | Grain | Contenu |
|---|---|---|
| `ventes.csv` | ligne de commande | SIMULÉ : prix plein, remise, tranche de remise, période commerciale, CA, coût, marge, jours depuis le lancement |
| `stock.csv` | variante | SIMULÉ : stock initial et final, pièces vendues, date de rupture, ventes perdues, alertes « retour en stock » |
| `releves.csv` | variante × jour de relevé | RÉEL : prix, remise, disponibilité, type et collection |
| `produits.csv`, `tailles.csv`, `tranches.csv`, `calendrier.csv`, `jours_lancement.csv` | dimensions | Le calendrier porte les moments sportifs réels et les périodes commerciales |
| `effet_moments.csv` | type de moment | Sortie de la régression du notebook |

Pour intégrer les nouveaux relevés quotidiens : relancer `src/prep_powerbi.py`, puis cliquer sur « Actualiser » dans Power BI.
