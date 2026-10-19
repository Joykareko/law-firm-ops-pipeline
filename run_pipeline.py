"""
Run the full pipeline:
    extract  ->  clean  ->  load staging  ->  quality checks  ->  build marts  ->  export for Power BI

    python run_pipeline.py

Outputs:
    data/warehouse.duckdb   the full warehouse (read by the Python prototype, app.py)
    data/powerbi/*.csv      a clean star schema to load into Power BI
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb

from pipeline.clean import clean_all
from pipeline.extract import extract_all
from pipeline.quality import run_checks

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "warehouse.duckdb"
MARTS = ROOT / "models" / "marts"
POWERBI_MODELS = ROOT / "models" / "powerbi"
POWERBI_OUT = ROOT / "data" / "powerbi"


def main() -> int:
    print("1/6 Extracting from CRM, practice management, billing and ad spend sources")
    raw = extract_all()
    for name, df in raw.items():
        print(f"     {name:<16} {len(df):>7,} rows")

    print("2/6 Cleaning and standardizing")
    clean, cleaning_log = clean_all(raw)

    print("3/6 Loading staging tables")
    DB_PATH.unlink(missing_ok=True)
    con = duckdb.connect(str(DB_PATH))
    for name, df in clean.items():
        con.register("tmp", df)
        con.execute(f"CREATE TABLE stg_{name} AS SELECT * FROM tmp")
        con.unregister("tmp")
    con.register("tmp", cleaning_log)
    con.execute("CREATE TABLE meta_cleaning_log AS SELECT * FROM tmp")
    con.unregister("tmp")

    print("4/6 Running data quality checks")
    checks = run_checks(con)
    con.register("tmp", checks)
    con.execute("CREATE TABLE meta_quality_checks AS SELECT * FROM tmp")
    con.unregister("tmp")
    for _, r in checks.iterrows():
        print(f"     [{r['status']:<4}] {r['check']} ({r['failing_rows']} rows)")
    if (checks["status"] == "FAIL").any():
        print("Pipeline stopped: a FAIL check must be fixed before marts are rebuilt.")
        return 1

    print("5/6 Building marts")
    for sql_file in sorted(MARTS.glob("*.sql")):
        con.execute(f"CREATE TABLE {sql_file.stem} AS {sql_file.read_text().rstrip().rstrip(';')}")
        n = con.execute(f"SELECT COUNT(*) FROM {sql_file.stem}").fetchone()[0]
        print(f"     {sql_file.stem:<22} {n:>6,} rows")

    print("6/6 Exporting star schema for Power BI")
    POWERBI_OUT.mkdir(parents=True, exist_ok=True)
    for sql_file in sorted(POWERBI_MODELS.glob("*.sql")):
        query = sql_file.read_text().rstrip().rstrip(";")
        con.execute(f"CREATE OR REPLACE TABLE pbi_{sql_file.stem} AS {query}")
        out = POWERBI_OUT / f"{sql_file.stem}.csv"
        con.execute(f"COPY pbi_{sql_file.stem} TO '{out.as_posix()}' (HEADER, DELIMITER ',')")
        n = con.execute(f"SELECT COUNT(*) FROM pbi_{sql_file.stem}").fetchone()[0]
        print(f"     {out.name:<26} {n:>6,} rows")
    for name, file in [("meta_quality_checks", "QualityChecks"), ("meta_cleaning_log", "CleaningLog")]:
        out = POWERBI_OUT / f"{file}.csv"
        con.execute(f"COPY {name} TO '{out.as_posix()}' (HEADER, DELIMITER ',')")

    con.close()
    print(f"Done. Warehouse written to {DB_PATH.relative_to(ROOT)}, Power BI files to {POWERBI_OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
