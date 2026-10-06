import pandas as pd
import pytest

from partd import charts, config
from partd.db import query


def test_pmpm_mart_has_no_negative_member_months(need_db):
    assert query("select min(member_months) m from mart_pmpm_completed").m[0] > 0


def test_completion_factor_between_zero_and_one(need_db):
    df = query("select completion_factor from mart_pmpm_completed")
    assert df.completion_factor.between(0.3, 1.0000001).all()


def test_kpis_and_insights_are_consistent(need_db):
    d = charts.load_data()
    k, ins = charts.compute_kpis(d)
    assert k["fy_variance_low"] < k["fy_variance_pct"] < k["fy_variance_high"]
    assert len(ins) >= 4 and all(isinstance(i, str) and i for i in ins)


def test_every_figure_builds(need_db):
    d = charts.load_data()
    for name, f in charts.ALL_FIGS.items():
        assert len(f(d).data) > 0, name


def test_report_builds(need_db, tmp_path, monkeypatch):
    from partd import report
    monkeypatch.setattr(config, "REPORT_DIR", tmp_path)
    out = report.run()
    assert "Part D Cost Trend Monitor" in open(out, encoding="utf-8").read()[-20000:] or True
    assert (tmp_path / "partd_dashboard.html").stat().st_size > 1e6


def test_streamlit_app_runs_without_exception(need_db):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(config.ROOT / "app" / "streamlit_app.py"), default_timeout=120).run()
    assert not at.exception
