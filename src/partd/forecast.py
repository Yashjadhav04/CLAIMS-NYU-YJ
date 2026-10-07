"""PMPM forecasting with a rolling-origin backtest.

Design choices (and why):

* The benefit design changed between 2024 (legacy, coverage gap) and 2025 (out-of-pocket cap), which changes both the
  level and the intra-year shape of plan liability. Forecasting across that break would mix two regimes, so models are
  fit on the post-redesign history only (Jan 2025 onward).
* Two transparent methods that suit ~20 monthly points, then their average:
    A. seasonal-naive with trailing growth: same month last year x (1 + trailing 3-month year-over-year growth)
    B. seasonal index x linear trend: seasonal factors from the first post-redesign year, linear trend on the
       deseasonalized series
  plus a no-seasonality "last value" baseline, so the backtest shows whether seasonality improves accuracy.
* Recent months are completion-adjusted (IBNR). Months with a completion factor below COMPLETION_MIN are excluded from
  backtest scoring because their "actual" is itself an estimate.
* The production method is whichever real model wins the backtest (it is not assumed in advance; with only a handful of
  backtest points the choice is provisional and is re-evaluated on every run).
* Intervals are empirical: +/- the error that 80% of backtest forecasts stayed within (floor 2%). Small sample.

Run:  PYTHONPATH=src python -m partd.forecast
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import config
from .db import query

REGIME_START = pd.Timestamp("2025-01-01")  # first month of the 2025+ benefit design
COMPLETION_MIN = 0.97
HORIZON = 3
MEASURES = {"net_plan_pmpm": "net_plan_liability", "gross_pmpm": "gross_drug_cost"}


# ---------------------------------------------------------------------------------------------- data
def load_monthly() -> pd.DataFrame:
    df = query(
        """
        select incurred_month as month,
               sum(member_months) as member_months,
               sum(net_plan_liability) as net_plan_liability,
               sum(gross_drug_cost) as gross_drug_cost,
               min(completion_factor) as completion_factor
        from mart_pmpm_completed
        group by 1 order by 1
        """
    )
    df["month"] = pd.to_datetime(df["month"])
    df["net_plan_pmpm"] = df["net_plan_liability"] / df["member_months"]
    df["gross_pmpm"] = df["gross_drug_cost"] / df["member_months"]
    return df


# ---------------------------------------------------------------------------------------------- methods
def method_last_value(y: np.ndarray, months: pd.DatetimeIndex, h: int) -> float:
    return float(y[-1])


def method_seasonal_naive_growth(y: np.ndarray, months: pd.DatetimeIndex, h: int, k: int = 3) -> float:
    n = len(y)
    if n < 12 + k:
        raise ValueError("need at least 12 + k observations")
    t = n - 1 + h
    growth = y[n - k : n].sum() / y[n - k - 12 : n - 12].sum()
    return float(y[t - 12] * growth)


def method_seasonal_trend(y: np.ndarray, months: pd.DatetimeIndex, h: int) -> float:
    n = len(y)
    if n < 12:
        raise ValueError("need at least 12 observations")
    first_year = y[:12]
    seas = {m.month: v / first_year.mean() for m, v in zip(months[:12], first_year)}
    s = np.array([seas[m.month] for m in months])
    d = y / s
    t = np.arange(n)
    b, a = np.polyfit(t, d, 1)
    target_month = (months[-1] + pd.DateOffset(months=h)).month
    return float((a + b * (n - 1 + h)) * seas[target_month])


def method_ensemble(y: np.ndarray, months: pd.DatetimeIndex, h: int) -> float:
    return 0.5 * (method_seasonal_naive_growth(y, months, h) + method_seasonal_trend(y, months, h))


METHODS = {
    "last_value (baseline)": method_last_value,
    "seasonal_naive_growth": method_seasonal_naive_growth,
    "seasonal_trend": method_seasonal_trend,
    "ensemble": method_ensemble,
}


# ---------------------------------------------------------------------------------------------- backtest
@dataclass
class Backtest:
    detail: pd.DataFrame
    summary: pd.DataFrame


def backtest(monthly: pd.DataFrame, value_col: str, min_origin: int = 15) -> Backtest:
    """Rolling-origin backtest on the regime-consistent, completion-mature part of the series."""
    m = monthly[(monthly["month"] >= REGIME_START) & (monthly["completion_factor"] >= COMPLETION_MIN)].reset_index(drop=True)
    y = m[value_col].to_numpy()
    months = pd.DatetimeIndex(m["month"])
    rows = []
    for n in range(min_origin, len(y)):
        for h in range(1, HORIZON + 1):
            if n - 1 + h >= len(y):
                continue
            actual = y[n - 1 + h]
            for name, fn in METHODS.items():
                pred = fn(y[:n], months[:n], h)
                rows.append(
                    {"origin_month": months[n - 1], "horizon": h, "target_month": months[n - 1 + h], "method": name,
                     "actual": actual, "forecast": pred, "rel_error": actual / pred - 1}
                )
    detail = pd.DataFrame(rows)
    summary = (
        detail.assign(abs_pct=lambda d: d["rel_error"].abs())
        .groupby("method")
        .agg(n_forecasts=("rel_error", "size"), mape=("abs_pct", "mean"), bias=("rel_error", "mean"),
             worst_abs_error=("abs_pct", "max"))
        .reset_index()
        .sort_values("mape")
    )
    return Backtest(detail, summary)


# ---------------------------------------------------------------------------------------------- forecast
def select_method(bt: Backtest) -> str:
    """Production method = lowest backtest MAPE among the real models (the last-value baseline is not eligible)."""
    eligible = bt.summary[~bt.summary["method"].str.contains("baseline")]
    return str(eligible.sort_values("mape").iloc[0]["method"])


def forecast_measure(monthly: pd.DataFrame, value_col: str, bt: Backtest) -> pd.DataFrame:
    m = monthly[monthly["month"] >= REGIME_START].reset_index(drop=True)
    y = m[value_col].to_numpy()
    months = pd.DatetimeIndex(m["month"])
    method = select_method(bt)
    errs = bt.detail[bt.detail["method"] == method]["rel_error"].abs().to_numpy()
    # Interval half-width: the error that 80% of backtest forecasts stayed within (floor 2%). Small sample.
    half = max(float(np.quantile(errs, 0.80)), 0.02)
    out = []
    for h in range(1, HORIZON + 1):
        point = METHODS[method](y, months, h)
        out.append(
            {
                "month": months[-1] + pd.DateOffset(months=h),
                "kind": "forecast",
                "value": point,
                "lower": point * (1 - half),
                "upper": point * (1 + half),
                "method": method,
            }
        )
    actual = pd.DataFrame({"month": months, "kind": "actual", "value": y, "lower": np.nan, "upper": np.nan, "method": ""})
    return pd.concat([actual, pd.DataFrame(out)], ignore_index=True)


def project_fy(monthly: pd.DataFrame, fc_net: pd.DataFrame, year: int = 2026) -> pd.DataFrame:
    """Full-year net plan liability: completed actuals to date + forecast PMPM x forecast member months."""
    act = monthly[monthly["month"].dt.year == year].copy()
    mm_last = act["member_months"].iloc[-1]
    mm_6 = monthly["member_months"].iloc[-7]
    g = (mm_last / mm_6) ** (1 / 6) - 1
    fc = fc_net[fc_net["kind"] == "forecast"].copy().reset_index(drop=True)
    fc["member_months"] = [mm_last * (1 + g) ** (i + 1) for i in range(len(fc))]
    budget = query("select month_start, budget_net_plan_pmpm from budget_net_plan_pmpm")
    budget["month_start"] = pd.to_datetime(budget["month_start"])
    bmap = dict(zip(budget["month_start"], budget["budget_net_plan_pmpm"]))

    actual_dollars = float(act["net_plan_liability"].sum())
    fc_dollars = {k: float((fc[k if k != "value" else "value"] * fc["member_months"]).sum()) for k in ("value", "lower", "upper")}
    budget_dollars = float(sum(bmap[m] * mm for m, mm in zip(act["month"], act["member_months"])) +
                           sum(bmap[m] * mm for m, mm in zip(fc["month"], fc["member_months"])))
    rows = []
    for label, fcv in (("low", fc_dollars["lower"]), ("base", fc_dollars["value"]), ("high", fc_dollars["upper"])):
        total = actual_dollars + fcv
        rows.append(
            {"scenario": label, "year": year, "actual_to_date": actual_dollars, "forecast_remaining": fcv,
             "projected_full_year": total, "budget_full_year": budget_dollars,
             "variance_dollars": total - budget_dollars, "variance_pct": total / budget_dollars - 1}
        )
    return pd.DataFrame(rows)


def run(verbose: bool = True) -> dict:
    monthly = load_monthly()
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results, summaries, fcs = {}, [], []
    for col in MEASURES:
        bt = backtest(monthly, col)
        fc = forecast_measure(monthly, col, bt)
        fc.insert(0, "measure", col)
        fcs.append(fc)
        s = bt.summary.copy()
        s.insert(0, "measure", col)
        summaries.append(s)
        bt.detail.assign(measure=col).to_csv(config.OUTPUT_DIR / f"backtest_detail_{col}.csv", index=False)
        results[col] = (bt, fc)

    pd.concat(fcs).to_csv(config.OUTPUT_DIR / "forecast_pmpm.csv", index=False)
    bt_summary = pd.concat(summaries)
    bt_summary.to_csv(config.OUTPUT_DIR / "forecast_backtest_summary.csv", index=False)
    fy = project_fy(monthly, results["net_plan_pmpm"][1])
    fy.to_csv(config.OUTPUT_DIR / "fy_projection.csv", index=False)

    summary = {
        "backtest": bt_summary.round(4).to_dict("records"),
        "fy_projection": fy.round(4).to_dict("records"),
    }
    (config.OUTPUT_DIR / "forecast_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    if verbose:
        pd.set_option("display.width", 200)
        print(bt_summary.round(4).to_string(index=False))
        print(fy.round(3).to_string(index=False))
    return summary


if __name__ == "__main__":
    run()
