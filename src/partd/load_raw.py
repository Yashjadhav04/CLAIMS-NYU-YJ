"""Load the generated raw files into DuckDB schema `raw` (the warehouse dbt reads from)."""
from __future__ import annotations

import duckdb

from . import config

TABLES = {
    "members": ("parquet", "members.parquet"),
    "plans": ("csv", "plans.csv"),
    "enrollment_monthly": ("parquet", "enrollment_monthly.parquet"),
    "pharmacies": ("parquet", "pharmacies.parquet"),
    "drugs": ("parquet", "drugs.parquet"),
    "pde_submissions": ("parquet", "pde_submissions.parquet"),
}


def load_raw(verbose: bool = True) -> None:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(config.DB_PATH))
    con.execute("create schema if not exists raw")
    for name, (fmt, fname) in TABLES.items():
        path = (config.RAW_DIR / fname).as_posix()
        reader = f"read_parquet('{path}')" if fmt == "parquet" else f"read_csv_auto('{path}')"
        con.execute(f"create or replace table raw.{name} as select * from {reader}")
        if verbose:
            n = con.execute(f"select count(*) from raw.{name}").fetchone()[0]
            print(f"raw.{name:<20} {n:>10,} rows")
    con.close()


if __name__ == "__main__":
    load_raw()
