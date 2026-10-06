"""Determinism and basic invariants of the synthetic generator (tiny population so it runs in seconds)."""
import shutil

import pandas as pd

from partd import config, generate


def _small(seed, root, monkeypatch):
    seeds = root / "seeds"
    seeds.mkdir(parents=True)
    for f in ("benefit_params.csv", "tier_cost_share.csv"):
        shutil.copy(config.SEEDS_DIR / f, seeds / f)
    monkeypatch.setattr(config, "RAW_DIR", root / "raw")
    monkeypatch.setattr(config, "OUTPUT_DIR", root / "out")
    monkeypatch.setattr(config, "SEEDS_DIR", seeds)
    generate.generate(n_members=150, seed=seed, verbose=False)
    return pd.read_parquet(root / "raw" / "pde_submissions.parquet")


def test_same_seed_same_output(tmp_path, monkeypatch):
    a = _small(7, tmp_path / "a", monkeypatch)
    b = _small(7, tmp_path / "b", monkeypatch)
    pd.testing.assert_frame_equal(a, b)
    c = _small(8, tmp_path / "c", monkeypatch)
    assert len(c) != len(a) or not a.equals(c)


def test_generated_money_identity(tmp_path, monkeypatch):
    a = _small(3, tmp_path / "a", monkeypatch)
    acc = a[a.dcs_status == "A"]
    resid = acc.gdcb + acc.gdca - (acc.patient_pay_amt + acc.lics_amt + acc.cpp_amt + acc.mfr_discount_amt)
    assert resid.abs().max() < 0.02
