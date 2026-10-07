"""Data loading, KPI/insight computation and Plotly figures shared by the HTML report and the Streamlit app.

Design rules followed (see docs/DESIGN_NOTES.md): one y-axis per chart, thin marks, fixed categorical colour order,
legend whenever there are 2+ series, selective direct labels, recessive grid, no colour-only encoding of status.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from . import config
from .db import query

# Validated reference palette (categorical slots 1-5, ink, chrome)
BLUE, ORANGE, AQUA, YELLOW, MAGENTA = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"
INK, INK2, MUTED, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
FONT = "system-ui, -apple-system, 'Segoe UI', sans-serif"


# ----------------------------------------------------------------------------------------------- data
def load_data() -> dict[str, pd.DataFrame]:
    q = query
    d: dict[str, pd.DataFrame] = {
        "bv": q("select * from mart_budget_variance order by incurred_month"),
        "pmpm_seg": q("select * from mart_pmpm_completed order by incurred_month"),
        "drivers": q("select * from mart_trend_drivers"),
        "by_drug": q("select * from mart_trend_by_drug"),
        "cat": q("select * from mart_catastrophic_penetration order by incurred_month"),
        "edits": q("select * from mart_pde_edit_monthly order by received_month, edit_code"),
        "completion": q("select * from mart_completion_curve order by dev_day"),
        "top_drugs": q("select * from mart_top_drugs_ytd where cost_rank <= 12 order by cost_rank"),
        "conc": q("select * from mart_cost_concentration order by benefit_year, cutoff"),
        "who_pays": q(
            """
            select incurred_month,
                   sum(net_plan_liability) as net_plan, sum(reinsurance_est) as reinsurance,
                   sum(mfr_discount) as mfr_discount, sum(lics) as lics, sum(patient_pay) as patient_pay,
                   sum(gross_drug_cost) as gross
            from mart_pmpm_completed group by 1 order by 1
            """
        ),
        "gdr": q(
            """
            select incurred_month, sum(generic_claims)::double / sum(claims) as gdr,
                   sum(specialty_gross) / sum(gross_drug_cost) as specialty_share
            from mart_pmpm_monthly group by 1 order by 1
            """
        ),
        "forecast": pd.read_csv(config.OUTPUT_DIR / "forecast_pmpm.csv", parse_dates=["month"]),
        "fy": pd.read_csv(config.OUTPUT_DIR / "fy_projection.csv"),
        "backtest": pd.read_csv(config.OUTPUT_DIR / "forecast_backtest_summary.csv"),
    }
    for k in ("bv", "pmpm_seg", "cat", "who_pays", "gdr"):
        d[k]["incurred_month"] = pd.to_datetime(d[k]["incurred_month"])
    d["edits"]["received_month"] = pd.to_datetime(d["edits"]["received_month"])
    return d


def compute_kpis(d: dict[str, pd.DataFrame]) -> tuple[dict, list[str]]:
    bv = d["bv"]
    cy = bv["benefit_year"].max()
    ytd = bv[bv["benefit_year"] == cy]
    ytd_act = ytd["actual_net_plan_pmpm"].mul(ytd["member_months"]).sum() / ytd["member_months"].sum()
    ytd_bud = ytd["budget_net_plan_pmpm"].mul(ytd["member_months"]).sum() / ytd["member_months"].sum()
    fy = d["fy"].set_index("scenario")
    base = fy.loc["base"]

    dr = d["drivers"].set_index("measure")
    g = dr.loc["gross_drug_cost"]
    n = dr.loc["net_plan_liability"]

    edits = d["edits"]
    last_full = edits["received_month"].sort_values().unique()[-2]  # latest complete month
    e_last = edits[edits["received_month"] == last_full]
    reject_rate_last = float(e_last["rejects"].sum() / e_last["submissions_in_month"].max())
    peak_row = edits.groupby("received_month").agg(r=("rejects", "sum"), s=("submissions_in_month", "max"))
    peak_row["rate"] = peak_row["r"] / peak_row["s"]
    peak_month = peak_row["rate"].idxmax()
    unresolved_dollars = float(edits["gross_at_risk_unresolved"].sum())
    top705 = edits[(edits["received_month"] == peak_month) & (edits["edit_code"] == "705")]["rejects"].sum()

    cat = d["cat"]
    sep = cat["incurred_month"].max()
    cat_now = float(cat[cat["incurred_month"] == sep]["pct_enrolled_in_catastrophic"].iloc[0])
    cat_prior = float(cat[cat["incurred_month"] == sep - pd.DateOffset(years=1)]["pct_enrolled_in_catastrophic"].iloc[0])

    movers = d["by_drug"][d["by_drug"]["measure"] == "gross_drug_cost"].sort_values("impact_rank").head(3)
    mover_txt = ", ".join(f"{r.drug_label} ({r.pmpm_change:+.1f})" for r in movers.itertuples())

    gdr_cy = d["gdr"][d["gdr"]["incurred_month"].dt.year == cy]["gdr"].mean()
    latest_cf = float(d["pmpm_seg"].groupby("incurred_month")["completion_factor"].min().iloc[-1])

    kpis = {
        "current_year": int(cy),
        "ytd_net_plan_pmpm": float(ytd_act),
        "ytd_budget_pmpm": float(ytd_bud),
        "ytd_variance_pct": float(ytd_act / ytd_bud - 1),
        "ytd_variance_dollars": float(ytd["variance_dollars"].sum()),
        "fy_projection": float(base["projected_full_year"]),
        "fy_budget": float(base["budget_full_year"]),
        "fy_variance_pct": float(base["variance_pct"]),
        "fy_variance_low": float(fy.loc["low", "variance_pct"]),
        "fy_variance_high": float(fy.loc["high", "variance_pct"]),
        "gross_trend_pct": float(g["pmpm_change_pct"]),
        "net_trend_pct": float(n["pmpm_change_pct"]),
        "gdr": float(gdr_cy),
        "reject_rate_last_full_month": reject_rate_last,
        "unresolved_dollars": unresolved_dollars,
        "cat_now": cat_now,
        "cat_prior": cat_prior,
        "latest_completion_factor": latest_cf,
    }
    insights = [
        f"Projected {cy} net plan liability is ${kpis['fy_projection']/1e6:.1f}M against a budget of ${kpis['fy_budget']/1e6:.1f}M, "
        f"a variance of {kpis['fy_variance_pct']:+.1%} (scenario range {kpis['fy_variance_low']:+.1%} to {kpis['fy_variance_high']:+.1%}). "
        f"Year-to-date variance is {kpis['ytd_variance_pct']:+.1%} (${kpis['ytd_variance_dollars']/1e6:.2f}M).",
        f"Gross drug cost PMPM increased {g['pmpm_change_pct']:.1%} year over year (YTD through "
        f"{pd.Timestamp(g['period_end']):%b %Y}): price {g['price_effect']:+.1f}, mix {g['mix_effect_existing'] + g['mix_effect_new_drugs']:+.1f}, "
        f"utilization {g['utilization_effect']:+.1f} ($ PMPM). Largest contributors by drug: {mover_txt}.",
        f"Catastrophic-phase penetration (members who have reached the out-of-pocket cap) was {cat_now:.1%} of enrolled members in "
        f"{sep:%b %Y}, compared with {cat_prior:.1%} a year earlier. Higher penetration moves a larger share of claims into the catastrophic phase.",
        f"PDE rejections peaked in {peak_month:%b %Y} at {peak_row.loc[peak_month, 'rate']:.1%} of submissions "
        f"(edit 705: {int(top705):,} of {int(peak_row.loc[peak_month, 'r']):,} rejections). Unresolved rejections represent "
        f"${unresolved_dollars/1e3:,.0f}K of gross drug cost not yet reflected in payment reconciliation.",
        f"The latest month is {latest_cf:.0%} complete as of the extract date; figures shown are completion-adjusted.",
    ]
    return kpis, insights


# ----------------------------------------------------------------------------------------------- figure helpers
def _base(fig: go.Figure, title: str, height: int = 380, yfmt: str | None = None, ytitle: str | None = None) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, x=0, xanchor="left", font=dict(size=15, color=INK, family=FONT)),
        height=height,
        margin=dict(l=56, r=24, t=56, b=44),
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font=dict(family=FONT, size=12, color=INK2),
        hovermode="x unified",
        legend=dict(orientation="h", y=-0.18, x=0, font=dict(size=12, color=INK2)),
        xaxis=dict(showgrid=False, linecolor=AXIS, tickcolor=AXIS, tickfont=dict(color=MUTED)),
        yaxis=dict(gridcolor=GRID, gridwidth=1, zeroline=False, linecolor="rgba(0,0,0,0)", tickfont=dict(color=MUTED),
                   tickformat=yfmt, title=dict(text=ytitle, font=dict(size=12, color=MUTED)) if ytitle else None),
    )
    return fig


# ----------------------------------------------------------------------------------------------- figures
def fig_pmpm_vs_budget(d: dict) -> go.Figure:
    bv = d["bv"]
    fc = d["forecast"]
    fc = fc[(fc["measure"] == "net_plan_pmpm")]
    act = fc[fc["kind"] == "actual"]
    pred = fc[fc["kind"] == "forecast"]
    last_act = act.iloc[-1]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=bv["incurred_month"], y=bv["budget_net_plan_pmpm"], name="Budget (synthetic bid)",
                             mode="lines", line=dict(color=MUTED, width=2, dash="dot"),
                             hovertemplate="$%{y:,.0f}"))
    fig.add_trace(go.Scatter(x=bv["incurred_month"], y=bv["actual_net_plan_pmpm"], name="Actual (completion-adjusted)",
                             mode="lines", line=dict(color=BLUE, width=2), hovertemplate="$%{y:,.0f}"))
    x_band = [last_act["month"], *pred["month"]]
    fig.add_trace(go.Scatter(x=[*x_band, *x_band[::-1]],
                             y=[last_act["value"], *pred["upper"], *pred["lower"][::-1], last_act["value"]],
                             fill="toself", fillcolor="rgba(235,104,52,0.15)", line=dict(width=0), mode="lines",
                             name="Forecast range", hoverinfo="skip", showlegend=True))
    fig.add_trace(go.Scatter(x=x_band, y=[last_act["value"], *pred["value"]], name="Forecast",
                             mode="lines+markers", line=dict(color=ORANGE, width=2, dash="dash"),
                             marker=dict(size=8, color=ORANGE, line=dict(width=2, color=SURFACE)),
                             hovertemplate="$%{y:,.0f}"))
    fig.add_annotation(x=bv["incurred_month"].iloc[-1], y=bv["actual_net_plan_pmpm"].iloc[-1], text="Sep: partially complete",
                       showarrow=True, arrowhead=0, ax=-70, ay=-34, font=dict(size=11, color=INK2), arrowcolor=AXIS)
    _base(fig, "Net plan liability PMPM: actual vs budget, with year-end forecast", yfmt="$,.0f", ytitle="$ per member per month")
    return fig


def fig_variance(d: dict) -> go.Figure:
    bv = d["bv"]
    fig = go.Figure(go.Bar(x=bv["incurred_month"], y=bv["variance_dollars"], name="Monthly variance to budget",
                           marker=dict(color=BLUE, line=dict(width=0)), hovertemplate="$%{y:,.0f}"))
    fig.update_traces(marker_cornerradius=4)
    _base(fig, "Monthly net plan liability variance to budget ($)", height=320, yfmt="$,.0s")
    return fig


def fig_trend_waterfall(d: dict, measure: str = "gross_drug_cost") -> go.Figure:
    r = d["drivers"].set_index("measure").loc[measure]
    labels = ["Prior-year YTD", "Utilization", "Mix", "New drugs", "Price", "Current YTD"]
    vals = [r["pmpm_prior"], r["utilization_effect"], r["mix_effect_existing"], r["mix_effect_new_drugs"], r["price_effect"], r["pmpm_current"]]
    text = [f"${vals[0]:,.0f}"] + [f"{v:+.1f}" for v in vals[1:5]] + [f"${vals[5]:,.0f}"]
    fig = go.Figure(go.Waterfall(
        x=labels, y=vals, measure=["absolute", "relative", "relative", "relative", "relative", "total"],
        text=text, textposition="outside", textfont=dict(color=INK2),
        increasing=dict(marker=dict(color=BLUE)), decreasing=dict(marker=dict(color=ORANGE)),
        totals=dict(marker=dict(color=MUTED)), connector=dict(line=dict(color=AXIS, width=1)),
        hovertemplate="%{x}: %{text}<extra></extra>"))
    lo = min(vals[0], vals[5]) * 0.9
    name = "Gross drug cost" if measure == "gross_drug_cost" else "Net plan liability"
    _base(fig, f"{name} PMPM: what drove the year-over-year change", height=360, yfmt="$,.0f")
    fig.update_yaxes(range=[lo, max(vals[0], vals[5]) * 1.05])
    fig.update_layout(hovermode="closest", showlegend=False)
    return fig


def fig_drug_movers(d: dict, measure: str = "gross_drug_cost") -> go.Figure:
    t = d["by_drug"]
    t = t[t["measure"] == measure].sort_values("impact_rank").head(10).sort_values("pmpm_change")
    fig = go.Figure()
    fig.add_trace(go.Bar(y=t["drug_label"], x=t["volume_effect"], name="Volume", orientation="h",
                         marker=dict(color=BLUE, line=dict(width=2, color=SURFACE)), hovertemplate="%{x:+.2f}"))
    fig.add_trace(go.Bar(y=t["drug_label"], x=t["price_effect"], name="Price", orientation="h",
                         marker=dict(color=ORANGE, line=dict(width=2, color=SURFACE)), hovertemplate="%{x:+.2f}"))
    _base(fig, "Top 10 drugs by change in PMPM, split into volume and price", height=420)
    fig.update_layout(barmode="relative", hovermode="y unified")
    fig.update_xaxes(title=dict(text="$ PMPM change", font=dict(size=12, color=MUTED)), gridcolor=GRID, showgrid=True)
    fig.update_yaxes(gridcolor="rgba(0,0,0,0)")
    return fig


def fig_who_pays(d: dict) -> go.Figure:
    w = d["who_pays"].copy()
    parts = [("net_plan", "Plan (net)", BLUE), ("reinsurance", "CMS reinsurance (est.)", ORANGE),
             ("mfr_discount", "Manufacturer discount", AQUA), ("lics", "Low-income subsidy", YELLOW),
             ("patient_pay", "Member", MAGENTA)]
    fig = go.Figure()
    for col, name, color in parts:
        fig.add_trace(go.Bar(x=w["incurred_month"], y=w[col] / w["gross"], name=name,
                             marker=dict(color=color, line=dict(width=1, color=SURFACE)),
                             hovertemplate="%{y:.1%}"))
    _base(fig, "Who pays the gross drug cost (share by month)", height=380, yfmt=".0%")
    fig.update_layout(barmode="stack")
    return fig


def fig_cat_penetration(d: dict) -> go.Figure:
    c = d["cat"].copy()
    c["m"] = c["incurred_month"].dt.month
    fig = go.Figure()
    colors = {2024: AQUA, 2025: ORANGE, 2026: BLUE}
    for yr, g in c.groupby("benefit_year"):
        fig.add_trace(go.Scatter(x=g["m"], y=g["pct_enrolled_in_catastrophic"], name=str(yr), mode="lines",
                                 line=dict(color=colors[yr], width=2), hovertemplate="%{y:.1%}"))
    _base(fig, "Members who have reached catastrophic coverage (cumulative within the year)", height=360, yfmt=".0%")
    fig.update_xaxes(tickmode="array", tickvals=list(range(1, 13)),
                     ticktext=["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
    fig.add_annotation(x=1, y=0, xref="paper", yref="paper", xanchor="left", yanchor="top", showarrow=False,
                       text="2024 = legacy design (catastrophic starts at $8,000 TrOOP); 2025+ = out-of-pocket cap",
                       font=dict(size=11, color=MUTED), yshift=-34, xshift=0)
    return fig


def fig_edits(d: dict) -> go.Figure:
    e = d["edits"]
    pivot = e.pivot_table(index="received_month", columns="edit_code", values="rejects", aggfunc="sum", fill_value=0)
    subs = e.groupby("received_month")["submissions_in_month"].max()
    rate = (pivot.sum(axis=1) / subs)
    colors = {"705": BLUE, "715": ORANGE, "738": AQUA, "999": YELLOW}
    labels = {"705": "705 no Part D enrollment", "715": "715 LICS not eligible", "738": "738 not a covered Part D drug", "999": "999 CMS internal"}
    fig = go.Figure()
    for code in pivot.columns:
        fig.add_trace(go.Bar(x=pivot.index, y=pivot[code], name=labels.get(code, code),
                             marker=dict(color=colors.get(code, MUTED), line=dict(width=1, color=SURFACE)),
                             hovertemplate="%{y:,.0f}"))
    peak = rate.idxmax()
    fig.add_annotation(x=peak, y=pivot.sum(axis=1).loc[peak], text=f"{rate.loc[peak]:.1%} of submissions rejected",
                       showarrow=True, ax=-80, ay=-10, arrowcolor=AXIS, font=dict(size=11, color=INK2))
    _base(fig, "PDE rejections by CMS edit code (month received)", height=380)
    fig.update_layout(barmode="stack")
    return fig


def fig_completion(d: dict) -> go.Figure:
    c = d["completion"]
    fig = go.Figure(go.Scatter(x=c["dev_day"], y=c["completion_factor"], mode="lines", name="Share of gross cost received",
                               line=dict(color=BLUE, width=2), hovertemplate="%{y:.1%}"))
    seg = d["pmpm_seg"].groupby("incurred_month").agg(dev=("dev_days_elapsed", "first"), cf=("completion_factor", "min")).reset_index()
    seg = seg[seg["cf"] < 0.999]
    fig.add_trace(go.Scatter(x=seg["dev"], y=seg["cf"], mode="markers+text", name="Recent months",
                             text=[f"{m:%b}" for m in seg["incurred_month"]], textposition="top left",
                             textfont=dict(size=11, color=INK2),
                             marker=dict(size=9, color=ORANGE, line=dict(width=2, color=SURFACE)), hovertemplate="%{y:.1%}"))
    _base(fig, "Claim completion curve: share of a month's cost received N days after month end", height=360, yfmt=".0%")
    fig.update_xaxes(title=dict(text="Days after month end", font=dict(size=12, color=MUTED)))
    fig.update_layout(hovermode="closest")
    return fig


def fig_top_drugs(d: dict) -> go.Figure:
    t = d["top_drugs"].sort_values("gross_pmpm")
    fig = go.Figure(go.Bar(y=t["drug_label"], x=t["gross_pmpm"], orientation="h", name="Gross PMPM",
                           marker=dict(color=BLUE, line=dict(width=0)), text=[f"{v:+.0%}" if pd.notna(v) else "" for v in t["gross_pmpm_yoy"]],
                           textposition="outside", textfont=dict(color=INK2, size=11),
                           hovertemplate="$%{x:,.2f} PMPM"))
    _base(fig, "Top 12 drugs by gross cost PMPM (label = year-over-year change)", height=420)
    fig.update_layout(showlegend=False, hovermode="closest")
    fig.update_xaxes(showgrid=True, gridcolor=GRID, tickprefix="$")
    fig.update_yaxes(gridcolor="rgba(0,0,0,0)")
    return fig


def fig_concentration(d: dict) -> go.Figure:
    c = d["conc"]
    fig = go.Figure()
    colors = {2024: AQUA, 2025: ORANGE, 2026: BLUE}
    for yr, g in c.groupby("benefit_year"):
        lab = f"{yr}" + (" (YTD)" if yr == c["benefit_year"].max() else "")
        fig.add_trace(go.Bar(x=g["bucket"], y=g["share_of_gross"], name=lab, marker=dict(color=colors[yr], line=dict(width=1, color=SURFACE)),
                             hovertemplate="%{y:.1%}"))
    _base(fig, "Cost concentration: share of annual gross drug cost by top members", height=340, yfmt=".0%")
    fig.update_layout(barmode="group", hovermode="x unified")
    return fig


def fig_pmpm_segments(df: pd.DataFrame, by: str, measure: str = "net_plan_liability") -> go.Figure:
    g = df.groupby(["incurred_month", by]).agg(v=(measure, "sum"), mm=("member_months", "sum")).reset_index()
    g["pmpm"] = g["v"] / g["mm"]
    palette = [BLUE, ORANGE, AQUA]
    fig = go.Figure()
    for i, (k, s) in enumerate(g.groupby(by)):
        name = {True: "LIS", False: "Non-LIS"}.get(k, str(k))
        fig.add_trace(go.Scatter(x=s["incurred_month"], y=s["pmpm"], name=name, mode="lines",
                                 line=dict(color=palette[i % 3], width=2), hovertemplate="$%{y:,.0f}"))
    label = "Net plan liability" if measure == "net_plan_liability" else "Gross drug cost"
    _base(fig, f"{label} PMPM by segment", height=360, yfmt="$,.0f")
    return fig


ALL_FIGS = {
    "pmpm_vs_budget": fig_pmpm_vs_budget,
    "variance": fig_variance,
    "waterfall_gross": lambda d: fig_trend_waterfall(d, "gross_drug_cost"),
    "waterfall_net": lambda d: fig_trend_waterfall(d, "net_plan_liability"),
    "movers": fig_drug_movers,
    "who_pays": fig_who_pays,
    "cat": fig_cat_penetration,
    "edits": fig_edits,
    "completion": fig_completion,
    "top_drugs": fig_top_drugs,
    "concentration": fig_concentration,
}
