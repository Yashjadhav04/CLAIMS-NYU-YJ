"""Export the marts as a star-schema-friendly folder for Power BI (or Tableau/Excel).

Run:  PYTHONPATH=src python -m partd.export_bi   ->  powerbi/export/*.csv + *.parquet
"""
from __future__ import annotations

import pandas as pd

from . import config
from .db import query

TABLES = {
    "fact_pmpm_monthly": "select * from mart_pmpm_completed",
    "fact_budget_variance": "select * from mart_budget_variance",
    "fact_trend_drivers": "select * from mart_trend_drivers",
    "fact_trend_by_drug": "select * from mart_trend_by_drug",
    "fact_benefit_phase_monthly": "select * from mart_benefit_phase_monthly",
    "fact_catastrophic_penetration": "select * from mart_catastrophic_penetration",
    "fact_pde_edits": "select * from mart_pde_edit_monthly",
    "fact_cost_concentration": "select * from mart_cost_concentration",
    "fact_top_drugs_ytd": "select * from mart_top_drugs_ytd",
    "dim_drug": "select * from stg_drugs",
    "dim_plan": "select * from stg_plans",
}


def run() -> list[str]:
    config.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for name, sql in TABLES.items():
        df = query(sql)
        df.to_csv(config.EXPORT_DIR / f"{name}.csv", index=False)
        df.to_parquet(config.EXPORT_DIR / f"{name}.parquet", index=False)
        written.append(name)
    for f in ("forecast_pmpm", "forecast_backtest_summary", "fy_projection"):
        src = config.OUTPUT_DIR / f"{f}.csv"
        if src.exists():
            pd.read_csv(src).to_csv(config.EXPORT_DIR / f"{f}.csv", index=False)
            written.append(f)
    dates = query("select distinct incurred_month as date from mart_pmpm_completed order by 1")
    dates["date"] = pd.to_datetime(dates["date"])
    dates["year"] = dates["date"].dt.year
    dates["month_num"] = dates["date"].dt.month
    dates["month_label"] = dates["date"].dt.strftime("%b %Y")
    dates.to_csv(config.EXPORT_DIR / "dim_date.csv", index=False)
    written.append("dim_date")
    print("exported", len(written), "tables to", config.EXPORT_DIR)
    return written


if __name__ == "__main__":
    run()
