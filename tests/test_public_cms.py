"""Tests on the real CMS public data (skipped if the files have not been downloaded)."""
import pandas as pd
import pytest

from partd import public_cms as p

pytestmark = pytest.mark.skipif(not p.ANNUAL.exists(), reason="run `make public` to download the CMS files")


@pytest.fixture(scope="module")
def d():
    return p.build_data()


def test_no_duplicate_drug_rows(d):
    assert not d["overall"].duplicated(["Brnd_Name", "Gnrc_Name"]).any()


def test_totals_in_plausible_range(d):
    t = d["totals"].set_index("year")["spend"]
    assert 150e9 < t[2020] < 250e9 and 250e9 < t[2024] < 350e9
    assert (t.diff().dropna() > 0).all()


def test_manufacturer_rows_reconcile_to_overall(d):
    mfr = d["mfr"].groupby(["Brnd_Name", "Gnrc_Name"])["Tot_Spndng_2024"].sum()
    ov = d["overall"].set_index(["Brnd_Name", "Gnrc_Name"])["Tot_Spndng_2024"]
    common = mfr.index.intersection(ov.index)
    ratio = mfr[common].sum() / ov[common].sum()
    assert 0.98 < ratio < 1.02


def test_pvm_identity_every_year_pair(d):
    for y0, y1 in zip(p.YEARS[:-1], p.YEARS[1:]):
        r = p.pvm(d["long"], y0, y1)  # raises if the identity is broken
        assert abs(r["volume"] + r["mix"] + r["price"] + r["new"] - (r["spend_to"] - r["spend_from"])) < 1.0


def test_pvm_identity_on_claims_basis(d):
    l = d["long"].assign(units=lambda x: x["claims"])
    l = l[l["units"] > 0]
    assert p.pvm(l, 2020, 2024)["spend_to"] > 0


def test_kpis_and_insights(d):
    k, ins = p.kpis(d)
    assert 0.05 < k["cagr"] < 0.15 and len(ins) >= 5


def test_every_figure_builds(d):
    for tab in p.FIGS.values():
        for _, fn in tab:
            assert len(fn(d).data) > 0
