"""Tests against the built pipeline outputs (skipped if the pipeline has not been run)."""
import numpy as np
import pandas as pd
import pytest

from partd import forecast
from partd.db import query


def test_pvm_identity_in_database(need_db):
    df = query("select measure, pmpm_change, utilization_effect, mix_effect_existing, mix_effect_new_drugs, price_effect from mart_trend_drivers")
    total = df.utilization_effect + df.mix_effect_existing + df.mix_effect_new_drugs + df.price_effect
    assert np.allclose(total, df.pmpm_change, atol=1e-6)


def test_forecast_methods_on_synthetic_series():
    months = pd.date_range("2025-01-01", periods=20, freq="MS")
    y = 100 * (1 + 0.01 * np.arange(20)) * (1 + 0.1 * np.sin(2 * np.pi * np.arange(20) / 12))
    for name, fn in forecast.METHODS.items():
        pred = fn(y, months, 1)
        assert np.isfinite(pred) and pred > 0, name
    # seasonality-aware methods should beat a flat last value on a clearly seasonal series
    truth = 100 * (1 + 0.01 * 20) * (1 + 0.1 * np.sin(2 * np.pi * 20 / 12))
    err_seasonal = abs(forecast.method_seasonal_naive_growth(y, months, 1) - truth)
    err_flat = abs(forecast.method_last_value(y, months, 1) - truth)
    assert err_seasonal < err_flat


def test_backtest_never_uses_future_data(need_db):
    m = forecast.load_monthly()
    bt = forecast.backtest(m, "net_plan_pmpm")
    assert (bt.detail["target_month"] > bt.detail["origin_month"]).all()
    assert bt.summary["mape"].between(0, 1).all()


def test_forecast_output_shape(need_db):
    fc = pd.read_csv(forecast.config.OUTPUT_DIR / "forecast_pmpm.csv")
    f = fc[(fc.kind == "forecast") & (fc.measure == "net_plan_pmpm")]
    assert len(f) == forecast.HORIZON
    assert (f.lower < f.value).all() and (f.value < f.upper).all()


def test_fy_projection_scenarios_ordered(need_db):
    fy = pd.read_csv(forecast.config.OUTPUT_DIR / "fy_projection.csv").set_index("scenario")
    assert fy.loc["low", "projected_full_year"] < fy.loc["base", "projected_full_year"] < fy.loc["high", "projected_full_year"]
