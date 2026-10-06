"""Tiny DuckDB helper shared by the forecast, dashboard and export code."""
from __future__ import annotations

import duckdb
import pandas as pd

from . import config


def connect(read_only: bool = True) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(config.DB_PATH), read_only=read_only)


def query(sql: str, params: list | None = None) -> pd.DataFrame:
    con = connect()
    try:
        return con.execute(sql, params or []).df()
    finally:
        con.close()
