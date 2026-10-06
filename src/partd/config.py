"""Central configuration. Everything is overridable with environment variables so CI can run a small build."""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("PARTD_DATA_DIR", ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"
OUTPUT_DIR = DATA_DIR / "outputs"
DB_PATH = Path(os.environ.get("PARTD_DB", DATA_DIR / "partd.duckdb"))
SEEDS_DIR = ROOT / "dbt_project" / "seeds"
EXPORT_DIR = ROOT / "powerbi" / "export"
REPORT_DIR = ROOT / "reports"

N_MEMBERS = int(os.environ.get("PARTD_MEMBERS", 6000))
RNG_SEED = int(os.environ.get("PARTD_SEED", 20261006))

# Simulation window (fill dates). The extract "as of" date controls how much of the latest month has been
# received, which is what creates realistic incompleteness (IBNR) in the most recent months.
START_DATE = date(2024, 1, 1)
END_DATE = date(2026, 9, 30)
AS_OF_DATE = date.fromisoformat(os.environ.get("PARTD_AS_OF", "2026-10-06"))

# Synthetic budget ("bid") assumption: 2026 budget PMPM = 2025 actual PMPM x (1 + BUDGET_TREND)
BUDGET_TREND = 0.07
