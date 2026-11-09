"""Charge les CSV (réels et simulés) dans DuckDB, lance chaque requête de sql/ et enregistre
le résultat dans data/output/<nom>.csv. À lancer depuis la racine du projet."""
import pathlib

import duckdb

ROOT = pathlib.Path(__file__).resolve().parents[1]
TABLES = {
    # simulées
    "produits": "data/clean/sim_produits.csv", "variantes": "data/clean/sim_variantes.csv",
    "clients": "data/clean/sim_clients.csv", "commandes": "data/clean/sim_commandes.csv",
    "lignes": "data/clean/sim_lignes.csv", "stock": "data/clean/sim_stock.csv",
    "alertes": "data/clean/sim_alertes_stock.csv", "evenements": "data/clean/sim_evenements.csv",
    "billets": "data/clean/sim_billets.csv", "liste_attente": "data/clean/sim_liste_attente.csv",
    "ab_test": "data/clean/sim_ab_test.csv",
    # réelles
    "resultats": "data/clean/kc_resultats_lol.csv",
    "releves_boutique": "data/raw/boutique/variants_snapshots.csv",
}

con = duckdb.connect()
for name, path in TABLES.items():
    con.execute(f"CREATE TABLE {name} AS SELECT * FROM read_csv_auto('{(ROOT / path).as_posix()}', header=true)")

out = ROOT / "data" / "output"
out.mkdir(exist_ok=True)
for q in sorted((ROOT / "sql").glob("*.sql")):
    df = con.execute(q.read_text(encoding="utf-8")).df()
    df.to_csv(out / f"{q.stem}.csv", index=False, encoding="utf-8")
    print(f"== {q.name} : {len(df)} lignes")
    print(df.head(8).to_string(index=False))
