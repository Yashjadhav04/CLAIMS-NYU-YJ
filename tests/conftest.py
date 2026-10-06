import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture(scope="session")
def has_db():
    from partd import config
    return config.DB_PATH.exists() and (config.OUTPUT_DIR / "forecast_pmpm.csv").exists()


@pytest.fixture()
def need_db(has_db):
    if not has_db:
        pytest.skip("pipeline not built; run `make all` first")
