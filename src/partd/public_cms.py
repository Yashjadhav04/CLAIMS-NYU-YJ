"""Real, public data: CMS Medicare Part D Spending by Drug (annual 2020-2024, plus the preliminary quarterly file for 2025).

Gross drug cost only (Medicare + plan + beneficiary payments, before any rebates). Drug-level totals across all of Medicare
Part D, not claim-level and not one plan: there are no member months here, so metrics are dollars, claims and dose units,
not PMPM. The synthetic pipeline stays separate; this module never touches it.

Run:  PYTHONPATH=src python -m partd.public_cms    ->  reports/partd_public_cms_dashboard.html
"""
from __future__ import annotations

import html
import json
import urllib.request

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.offline import get_plotlyjs

from . import config
from .charts import AQUA, AXIS, BLUE, GRID, INK2, MAGENTA, MUTED, ORANGE, SURFACE, YELLOW, _base
from . import public_extra as X
from .report import CSS, JS

PUBLIC_DIR = config.DATA_DIR / "public"
ANNUAL = PUBLIC_DIR / "cms_partd_spending_by_drug_annual.csv"
QUARTERLY = PUBLIC_DIR / "cms_partd_spending_by_drug_quarterly.csv"
CATALOG = "https://data.cms.gov/data.json"
YEARS = [2020, 2021, 2022, 2023, 2024]
GLP1 = ["semaglutide", "tirzepatide", "dulaglutide", "liraglutide", "exenatide", "lixisenatide"]


# ----------------------------------------------------------------------------------------------- fetch
def _csv_url(title_prefix: str) -> str:
    """Resolve the latest CSV link from CMS's catalogue (file names change with every release)."""
    with urllib.request.urlopen(CATALOG, timeout=120) as r:
        cat = json.load(r)
    hits = [ds for ds in cat["dataset"] if ds["title"].startswith(title_prefix)]
    for ds in sorted(hits, key=lambda d: d["title"], reverse=True):  # titles end in the data date, so newest first
        for dist in ds.get("distribution", []):
            if dist.get("format") == "CSV":
                return dist.get("downloadURL") or dist["accessURL"]
    raise RuntimeError(f"no CSV found for {title_prefix!r}")


def fetch(force: bool = False) -> None:
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    for path, prefix in ((ANNUAL, "Medicare Part D Spending by Drug"), (QUARTERLY, "Medicare Quarterly Part D Spending by Drug"),
                         (X.ENROLL, "Medicare Monthly Enrollment"), (X.GEO, "Medicare Part D Prescribers - by Geography and Drug")):
        if force or not path.exists():
            url = _csv_url(prefix)
            print("downloading", url)
            urllib.request.urlretrieve(url, path)


# ----------------------------------------------------------------------------------------------- tidy
def load_annual() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (drug-level 'Overall' rows, manufacturer-level rows)."""
    a = pd.read_csv(ANNUAL)
    overall = a[a["Mftr_Name"] == "Overall"].copy()
    mfr = a[a["Mftr_Name"] != "Overall"].copy()
    return overall, mfr


def long_drug_year(overall: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for y in YEARS:
        d = overall[["Brnd_Name", "Gnrc_Name"]].copy()
        d["year"] = y
        d["spend"] = overall[f"Tot_Spndng_{y}"]
        d["units"] = overall[f"Tot_Dsg_Unts_{y}"]
        d["claims"] = overall[f"Tot_Clms_{y}"]
        d["benes"] = overall[f"Tot_Benes_{y}"]
        rows.append(d)
    long = pd.concat(rows, ignore_index=True)
    return long[(long["spend"] > 0) & (long["units"] > 0)].reset_index(drop=True)


def load_2025() -> pd.DataFrame:
    q = pd.read_csv(QUARTERLY, usecols=range(10))
    q = q[(q["Mftr_Name"] == "Overall") & q["Year"].str.startswith("2025")]
    return q.rename(columns={"Tot_Spndng": "spend", "Tot_Clms": "claims", "Tot_Benes": "benes"})[
        ["Brnd_Name", "Gnrc_Name", "spend", "claims", "benes"]
    ]


# ----------------------------------------------------------------------------------------------- analysis
def pvm(long: pd.DataFrame, y0: int, y1: int) -> dict:
    """Spend change split into volume, mix, price and new-drug effects (units = dose units).

    Same algebra as the synthetic pipeline's mart_trend_drivers, with total dollars instead of PMPM:
      volume = (U1/U0 - 1) * S0;  mix = sum[(u1 - u0*U1/U0) * p0] over drugs present in y0;  price = sum[u1*(p1-p0)];
      new = sum[u1*p1] over drugs absent in y0.  Sum equals S1 - S0 exactly.
    Dose units mix tablets, mL and pens, so 'mix' also absorbs unit heterogeneity: read it as 'shift between drugs'.
    """
    a = long[long["year"] == y0].set_index(["Brnd_Name", "Gnrc_Name"])
    b = long[long["year"] == y1].set_index(["Brnd_Name", "Gnrc_Name"])
    idx = a.index.union(b.index)
    u0 = a["units"].reindex(idx).fillna(0)
    u1 = b["units"].reindex(idx).fillna(0)
    s0 = a["spend"].reindex(idx).fillna(0)
    s1 = b["spend"].reindex(idx).fillna(0)
    p0 = (s0 / u0.where(u0 > 0)).fillna(0)
    p1 = (s1 / u1.where(u1 > 0)).fillna(0)
    in0 = u0 > 0
    U0, U1, S0, S1 = u0.sum(), u1.sum(), s0.sum(), s1.sum()
    volume = (U1 / U0 - 1) * S0
    mix = float(((u1 - u0 * U1 / U0) * p0)[in0].sum())
    both = in0 & (u1 > 0)
    price = float((u1 * (p1 - p0))[both].sum())
    new = float((u1 * p1)[~in0].sum())
    assert abs(volume + mix + price + new - (S1 - S0)) < 1.0, "PVM identity broken"
    return {"from": y0, "to": y1, "spend_from": S0, "spend_to": S1, "volume": volume, "mix": mix, "price": price, "new": new}


def price_effect_by_drug(long: pd.DataFrame, y0: int, y1: int) -> pd.DataFrame:
    a = long[long["year"] == y0].set_index(["Brnd_Name", "Gnrc_Name"])
    b = long[long["year"] == y1].set_index(["Brnd_Name", "Gnrc_Name"])
    j = a.join(b, lsuffix="0", rsuffix="1", how="inner")
    j["price_effect"] = j["units1"] * (j["spend1"] / j["units1"] - j["spend0"] / j["units0"])
    return j.reset_index()


def build_data() -> dict:
    overall, mfr = load_annual()
    long = long_drug_year(overall)
    d = {"overall": overall, "mfr": mfr, "long": long, "q25": load_2025()}
    d["totals"] = (long.groupby("year").agg(spend=("spend", "sum"), claims=("claims", "sum"), units=("units", "sum")).reset_index())
    d["pvm"] = pd.DataFrame([pvm(long, y, y + 1) for y in YEARS[:-1]])
    d["pvm_total"] = pvm(long, 2020, 2024)
    e = X.load_enrollment()
    d["enroll_monthly"] = X.national_monthly(e)
    d["member_months"] = X.annual_member_months(d["enroll_monthly"])
    d["natl"] = X.national_pmpm(d["totals"], d["member_months"])
    d["bridge"] = pd.DataFrame([X.pmpm_bridge(d["natl"], y, y + 1) for y in YEARS[:-1]])
    d["geo"] = X.load_geo()
    d["states"] = X.state_pmpm(e, d["geo"])
    d["negotiation"] = X.negotiation_table()
    d["recon"] = X.reconciliation(d["totals"], d["geo"], e, overall)
    return d


def kpis(d: dict) -> tuple[dict, list[str]]:
    t = d["totals"].set_index("year")
    cagr = (t.loc[2024, "spend"] / t.loc[2020, "spend"]) ** 0.25 - 1
    l24 = d["long"][d["long"]["year"] == 2024].sort_values("spend", ascending=False)
    top10 = l24.head(10)["spend"].sum() / l24["spend"].sum()
    p = d["pvm_total"]
    g = d["long"][d["long"]["Gnrc_Name"].str.lower().str.contains("|".join(GLP1))].groupby("year")["spend"].sum()
    q25 = d["q25"]
    nat = d["natl"].set_index("year")
    neg = d["negotiation"]
    k = {
        "pmpm_2024": nat.loc[2024, "gross_pmpm"], "pmpm_2020": nat.loc[2020, "gross_pmpm"], "avg_enrollees_2024": nat.loc[2024, "avg_enrollees"],
        "neg_spend": neg["spend_2024"].sum(), "neg_share": neg["spend_2024"].sum() / t.loc[2024, "spend"],
        "neg_implied": neg["implied_gross_reduction_2024_volume"].sum(),
        "spend_2024": t.loc[2024, "spend"], "spend_2020": t.loc[2020, "spend"], "cagr": cagr,
        "claims_2024": t.loc[2024, "claims"], "top10_share": top10, "top_drug": l24.iloc[0]["Brnd_Name"],
        "top_drug_spend": l24.iloc[0]["spend"], "glp1_2024": g[2024], "glp1_2020": g[2020],
        "claims_cagr": (t.loc[2024, "claims"] / t.loc[2020, "claims"]) ** 0.25 - 1,
        "spend_2025_prelim": q25["spend"].sum(),
    }
    pe = d["pvm"]
    early = pe[pe["to"] <= 2023]["price"].sum()
    last = pe[pe["to"] == 2024].iloc[0]
    j = price_effect_by_drug(d["long"], 2023, 2024)
    ins_mask = j["Gnrc_Name"].str.lower().str.contains("insulin")
    insulin_pe = j.loc[ins_mask, "price_effect"].sum()
    n_down, n_up = int((j["price_effect"] < 0).sum()), int((j["price_effect"] > 0).sum())
    lantus = d["overall"][d["overall"]["Brnd_Name"] == "Lantus Solostar"].iloc[0]
    k["insulin_price_effect"] = insulin_pe
    ins = [
        f"Medicare Part D gross drug spending grew from ${k['spend_2020']/1e9:,.0f}B in 2020 to ${k['spend_2024']/1e9:,.0f}B in 2024, "
        f"{cagr:.1%} a year, while claims grew {k['claims_cagr']:.1%} a year. Spending per claim rose faster than volume.",
        f"Price effects added ${early/1e9:,.0f}B across 2020 to 2023, then subtracted ${-last['price']/1e9:,.0f}B in 2024. "
        f"Insulin accounts for ${-insulin_pe/1e9:,.0f}B of the drop: Lantus Solostar's spend per dose unit fell from "
        f"${lantus['Avg_Spnd_Per_Dsg_Unt_Wghtd_2023']:.2f} to ${lantus['Avg_Spnd_Per_Dsg_Unt_Wghtd_2024']:.2f}, in line with the insulin list-price cuts announced for 2024. "
        f"The rest is spread across the other drugs ({n_down:,} drugs had lower spend per unit, {n_up:,} higher); I have not attributed it further.",
        f"Volume (${last['volume']/1e9:,.0f}B) and a shift toward higher-cost drugs (${last['mix']/1e9:,.0f}B) drove the 2024 increase instead.",
        f"Per member, gross cost went from ${k['pmpm_2020']:,.0f} to ${k['pmpm_2024']:,.0f} a month between 2020 and 2024 "
        f"({nat.loc[2024, 'avg_enrollees']/1e6:,.1f}M average Part D enrollees in 2024, {nat.loc[2024, 'mapd_share']:.0%} in MA-PD plans). It was flat from 2023 to 2024.",
        f"The ten drugs Medicare negotiated for 2026 were ${k['neg_spend']/1e9:,.0f}B, or {k['neg_share']:.0%}, of 2024 gross spend. "
        f"Their spend per claim in Q1 2026 data is already {-neg['observed_change_per_claim'].max():.0%} to {-neg['observed_change_per_claim'].min():.0%} lower than 2025 for most of them, "
        "close to the announced price cuts (NovoLog is the exception because its list price was cut in 2024). Q1 2026 is preliminary.",
        f"GLP-1 diabetes and weight-loss drugs went from ${k['glp1_2020']/1e9:,.1f}B to ${k['glp1_2024']/1e9:,.1f}B ({k['glp1_2024']/k['spend_2024']:.1%} of 2024 spending).",
        f"The ten largest drugs make up {top10:.0%} of 2024 spending; {k['top_drug']} alone is ${k['top_drug_spend']/1e9:,.1f}B.",
        "The 2025 figure comes from CMS's preliminary quarterly file, which CMS says is not directly comparable to the annual file, so it is shown as a single number and left out of growth rates.",
    ]
    return k, ins


# ----------------------------------------------------------------------------------------------- figures
def fig_spend_claims(d: dict) -> go.Figure:
    t = d["totals"]
    idx = t["spend"] / t["spend"].iloc[0] * 100
    cl = t["claims"] / t["claims"].iloc[0] * 100
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=t["year"], y=idx, name="Gross spend", mode="lines+markers", line=dict(color=BLUE, width=2),
                             marker=dict(size=8, line=dict(width=2, color=SURFACE)), hovertemplate="%{y:.0f}"))
    fig.add_trace(go.Scatter(x=t["year"], y=cl, name="Claims", mode="lines+markers", line=dict(color=ORANGE, width=2),
                             marker=dict(size=8, line=dict(width=2, color=SURFACE)), hovertemplate="%{y:.0f}"))
    fig.add_annotation(x=2024, y=idx.iloc[-1], text=f"Spend {idx.iloc[-1]:.0f}", showarrow=False, xanchor="left", xshift=10, font=dict(color=INK2))
    fig.add_annotation(x=2024, y=cl.iloc[-1], text=f"Claims {cl.iloc[-1]:.0f}", showarrow=False, xanchor="left", xshift=10, font=dict(color=INK2))
    _base(fig, f"Spend rose {idx.iloc[-1]-100:.0f}% from 2020 to 2024; claims rose {cl.iloc[-1]-100:.0f}% (index, 2020 = 100)", height=360)
    fig.update_xaxes(tickmode="array", tickvals=YEARS, range=[2019.8, 2024.6])
    return fig


def fig_pvm_years(d: dict) -> go.Figure:
    p = d["pvm"]
    labels = [f"{a} to {b}" for a, b in zip(p["from"], p["to"])]
    fig = go.Figure()
    for col, name, color in (("price", "Price", ORANGE), ("volume", "Volume", BLUE), ("mix", "Mix between drugs", AQUA), ("new", "New drugs", YELLOW)):
        fig.add_trace(go.Bar(x=labels, y=p[col] / 1e9, name=name, marker=dict(color=color, line=dict(width=2, color=SURFACE)),
                             hovertemplate="$%{y:.1f}B"))
    _base(fig, "What drove the yearly increase in gross spend ($ billions)", height=400)
    fig.update_layout(barmode="relative", hovermode="x unified")
    return fig


def fig_top_drugs(d: dict, n: int = 15) -> go.Figure:
    l = d["long"]
    b = l[l["year"] == 2024]
    t = b.sort_values("spend", ascending=False).head(n).iloc[::-1]
    fig = go.Figure(go.Bar(y=t["Brnd_Name"], x=t["spend"] / 1e9, orientation="h", marker=dict(color=BLUE, line=dict(width=2, color=SURFACE)),
                           text=[f"${v/1e9:.1f}B" for v in t["spend"]], textposition="outside", textfont=dict(color=INK2),
                           hovertemplate="%{y}: $%{x:.2f}B<extra></extra>"))
    _base(fig, f"Top {n} drugs by 2024 gross spend ($ billions)", height=470)
    fig.update_layout(hovermode="closest", showlegend=False, margin=dict(l=130, r=60, t=56, b=40))
    fig.update_xaxes(gridcolor=GRID, showgrid=True)
    fig.update_yaxes(gridcolor="rgba(0,0,0,0)")
    return fig


def fig_movers(d: dict, n: int = 10) -> go.Figure:
    l = d["long"]
    a = l[l["year"] == 2020].set_index(["Brnd_Name", "Gnrc_Name"])["spend"]
    b = l[l["year"] == 2024].set_index(["Brnd_Name", "Gnrc_Name"])["spend"]
    ch = (b.reindex(a.index.union(b.index)).fillna(0) - a.reindex(a.index.union(b.index)).fillna(0)).sort_values()
    t = pd.concat([ch.head(5), ch.tail(n)]).reset_index()
    t.columns = ["Brnd_Name", "Gnrc_Name", "chg"]
    colors = [ORANGE if v < 0 else BLUE for v in t["chg"]]
    fig = go.Figure(go.Bar(y=t["Brnd_Name"], x=t["chg"] / 1e9, orientation="h", marker=dict(color=colors, line=dict(width=2, color=SURFACE)),
                           text=[f"{v/1e9:+.1f}B" for v in t["chg"]], textposition="outside", textfont=dict(color=INK2),
                           hovertemplate="%{y}: %{x:+.2f}B<extra></extra>"))
    _base(fig, "Biggest changes in gross spend, 2020 to 2024 ($ billions; blue up, orange down)", height=470)
    fig.update_layout(hovermode="closest", showlegend=False, margin=dict(l=130, r=60, t=56, b=40))
    fig.update_xaxes(gridcolor=GRID, showgrid=True)
    fig.update_yaxes(gridcolor="rgba(0,0,0,0)")
    return fig


def fig_glp1(d: dict) -> go.Figure:
    l = d["long"]
    g = l[l["Gnrc_Name"].str.lower().str.contains("|".join(GLP1))]
    piv = g.assign(Gnrc_Name=g["Gnrc_Name"].str.split().str[0].str.title()).groupby(["year", "Gnrc_Name"])["spend"].sum().unstack(fill_value=0) / 1e9
    order = piv.sum().sort_values(ascending=False).index.tolist()
    palette = [BLUE, ORANGE, AQUA, YELLOW, MAGENTA, MUTED]
    fig = go.Figure()
    for i, c in enumerate(order[:5]):
        fig.add_trace(go.Bar(x=piv.index, y=piv[c], name=c, marker=dict(color=palette[i], line=dict(width=2, color=SURFACE)), hovertemplate="$%{y:.2f}B"))
    rest = piv[order[5:]].sum(axis=1) if len(order) > 5 else None
    if rest is not None and rest.sum() > 0:
        fig.add_trace(go.Bar(x=piv.index, y=rest, name="Other", marker=dict(color=palette[5], line=dict(width=2, color=SURFACE)), hovertemplate="$%{y:.2f}B"))
    _base(fig, "GLP-1 drugs: gross spend by active ingredient ($ billions)", height=380)
    fig.update_layout(barmode="stack")
    fig.update_xaxes(tickmode="array", tickvals=YEARS)
    return fig


def fig_concentration(d: dict) -> go.Figure:
    rows = []
    for y, g in d["long"].groupby("year"):
        s = g["spend"].sort_values(ascending=False)
        rows.append({"year": y, **{f"Top {n}": s.head(n).sum() / s.sum() for n in (10, 50, 100)}})
    t = pd.DataFrame(rows)
    fig = go.Figure()
    for c, color in (("Top 10", BLUE), ("Top 50", ORANGE), ("Top 100", AQUA)):
        fig.add_trace(go.Scatter(x=t["year"], y=t[c], name=c, mode="lines+markers", line=dict(color=color, width=2),
                                 marker=dict(size=8, line=dict(width=2, color=SURFACE)), hovertemplate="%{y:.1%}"))
    _base(fig, "Share of gross spend from the largest drugs", height=360, yfmt=".0%")
    fig.update_xaxes(tickmode="array", tickvals=YEARS)
    return fig


def fig_manufacturers(d: dict, n: int = 12) -> go.Figure:
    m = d["mfr"].groupby("Mftr_Name")["Tot_Spndng_2024"].sum().sort_values(ascending=False).head(n).iloc[::-1]
    fig = go.Figure(go.Bar(y=m.index, x=m.values / 1e9, orientation="h", marker=dict(color=BLUE, line=dict(width=2, color=SURFACE)),
                           text=[f"${v/1e9:.1f}B" for v in m.values], textposition="outside", textfont=dict(color=INK2),
                           hovertemplate="%{y}: $%{x:.2f}B<extra></extra>"))
    _base(fig, f"Top {n} manufacturers by 2024 gross spend ($ billions)", height=440)
    fig.update_layout(hovermode="closest", showlegend=False, margin=dict(l=170, r=60, t=56, b=40))
    fig.update_xaxes(gridcolor=GRID, showgrid=True)
    fig.update_yaxes(gridcolor="rgba(0,0,0,0)")
    return fig


def fig_unit_price(d: dict, n: int = 40) -> go.Figure:
    """Distribution of 2023-2024 change in spend per dose unit among the largest drugs (spend-weighted view is in the PVM chart)."""
    o = d["overall"]
    top = o.sort_values("Tot_Spndng_2024", ascending=False).head(n)
    v = (top["Chg_Avg_Spnd_Per_Dsg_Unt_23_24"].dropna() * 100)
    med = float(np.median(v))
    fig = go.Figure(go.Histogram(x=v, xbins=dict(size=2), marker=dict(color=BLUE, line=dict(width=2, color=SURFACE)), hovertemplate="%{x}%: %{y} drugs"))
    fig.add_vline(x=med, line=dict(color=ORANGE, width=2, dash="dash"), annotation_text=f"median {med:+.1f}%", annotation_font=dict(color=INK2))
    _base(fig, f"Change in spend per dose unit, 2023 to 2024, for the {n} largest drugs (% change)", height=340)
    fig.update_layout(hovermode="closest", showlegend=False)
    fig.update_yaxes(title=dict(text="number of drugs", font=dict(size=12, color=MUTED)))
    return fig


def fig_pmpm_national(d: dict) -> go.Figure:
    t = d["natl"]
    fig = go.Figure(go.Scatter(x=t["year"], y=t["gross_pmpm"], mode="lines+markers+text", line=dict(color=BLUE, width=2),
                               marker=dict(size=8, line=dict(width=2, color=SURFACE)), text=[f"${v:,.0f}" for v in t["gross_pmpm"]],
                               textposition="top center", textfont=dict(color=INK2), hovertemplate="$%{y:,.0f}"))
    _base(fig, "Gross drug cost per Part D member per month (real enrollment as denominator)", height=340, yfmt="$,.0f")
    fig.update_layout(showlegend=False)
    fig.update_xaxes(tickmode="array", tickvals=YEARS)
    fig.update_yaxes(range=[t["gross_pmpm"].min() * 0.85, t["gross_pmpm"].max() * 1.08])
    return fig


def fig_pmpm_bridge(d: dict) -> go.Figure:
    b = d["bridge"]
    labels = [f"{a} to {c}" for a, c in zip(b["from"], b["to"])]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=labels, y=b["cost_per_claim"], name="Cost per claim", marker=dict(color=ORANGE, line=dict(width=2, color=SURFACE)), hovertemplate="$%{y:+.1f}"))
    fig.add_trace(go.Bar(x=labels, y=b["utilization"], name="Claims per member", marker=dict(color=BLUE, line=dict(width=2, color=SURFACE)), hovertemplate="$%{y:+.1f}"))
    _base(fig, "Change in gross PMPM: claims per member vs cost per claim ($ per member per month)", height=360)
    fig.update_layout(barmode="relative")
    return fig


def fig_enrollment_mix(d: dict) -> go.Figure:
    n = d["enroll_monthly"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=n["date"], y=n["mapd"] / 1e6, name="MA-PD (Medicare Advantage)", mode="lines", stackgroup="one", line=dict(width=0.5, color=SURFACE), fillcolor=BLUE, hovertemplate="%{y:.1f}M"))
    fig.add_trace(go.Scatter(x=n["date"], y=n["pdp"] / 1e6, name="Stand-alone PDP", mode="lines", stackgroup="one", line=dict(width=0.5, color=SURFACE), fillcolor=ORANGE, hovertemplate="%{y:.1f}M"))
    _base(fig, "Part D enrollees by plan type (millions; monthly, to latest month)", height=340)
    return fig


def fig_state_ranked(d: dict, n: int = 10) -> go.Figure:
    s = d["states"].sort_values("gross_pmpm")
    t = pd.concat([s.head(n), s.tail(n)])
    med = float(s["gross_pmpm"].median())
    colors = [AQUA] * n + [BLUE] * n  # low states first (sorted ascending), then high
    fig = go.Figure(go.Bar(y=t["state"], x=t["gross_pmpm"], orientation="h", marker=dict(color=colors, line=dict(width=2, color=SURFACE)),
                           text=[f"${v:,.0f}" for v in t["gross_pmpm"]], textposition="outside", textfont=dict(color=INK2),
                           hovertemplate="%{y}: $%{x:,.0f}<extra></extra>"))
    fig.add_vline(x=med, line=dict(color=MUTED, width=1, dash="dot"), annotation_text=f"median ${med:,.0f}", annotation_position="bottom right", annotation_font=dict(color=INK2))
    _base(fig, f"Gross drug cost per member per month, 2024: {n} highest (blue) and {n} lowest (green) states", height=560)
    fig.update_layout(hovermode="closest", showlegend=False, margin=dict(l=60, r=70, t=56, b=40))
    fig.update_xaxes(gridcolor=GRID, showgrid=True, tickformat="$,.0f")
    fig.update_yaxes(gridcolor="rgba(0,0,0,0)")
    return fig


def fig_state_scatter(d: dict) -> go.Figure:
    s = d["states"]
    fig = go.Figure(go.Scatter(x=s["fills_per_member_month"], y=s["cost_per_fill"], mode="markers+text", text=s["state"], textposition="top center",
                               textfont=dict(size=9, color=MUTED), marker=dict(size=9, color=BLUE, line=dict(width=2, color=SURFACE)),
                               hovertemplate="%{text}: %{x:.2f} fills, $%{y:,.0f} per fill<extra></extra>"))
    _base(fig, "States differ on two things: fills per member (use) and cost per 30-day fill (price and drug mix)", height=480, yfmt="$,.0f")
    fig.update_layout(hovermode="closest", showlegend=False)
    fig.update_xaxes(title=dict(text="30-day fills per member per month", font=dict(size=12, color=MUTED)))
    return fig


def fig_negotiation(d: dict) -> go.Figure:
    n = d["negotiation"].sort_values("spend_2024")
    fig = go.Figure()
    fig.add_trace(go.Bar(y=n["drug"], x=n["mfp_discount"] * 100, name="Announced price cut (MFP vs list)", orientation="h", marker=dict(color=BLUE, line=dict(width=2, color=SURFACE)), hovertemplate="%{x:.0f}%"))
    fig.add_trace(go.Bar(y=n["drug"], x=-n["observed_change_per_claim"] * 100, name="Observed drop in spend per claim, Q1 2026 vs 2025", orientation="h", marker=dict(color=ORANGE, line=dict(width=2, color=SURFACE)), hovertemplate="%{x:.0f}%"))
    _base(fig, "The 10 drugs with negotiated 2026 prices: announced cut vs what Q1 2026 data shows (%)", height=520)
    fig.update_layout(barmode="group", hovermode="y unified", margin=dict(l=110, r=30, t=56, b=60))
    fig.update_xaxes(gridcolor=GRID, showgrid=True)
    fig.update_yaxes(gridcolor="rgba(0,0,0,0)")
    return fig


def fig_negotiation_exposure(d: dict) -> go.Figure:
    n = d["negotiation"].sort_values("spend_2024")
    fig = go.Figure(go.Bar(y=n["drug"], x=n["spend_2024"] / 1e9, orientation="h", marker=dict(color=BLUE, line=dict(width=2, color=SURFACE)),
                           text=[f"${v/1e9:.1f}B" for v in n["spend_2024"]], textposition="outside", textfont=dict(color=INK2), hovertemplate="%{y}: $%{x:.2f}B<extra></extra>"))
    _base(fig, "2024 gross spend on the 10 negotiated drugs ($ billions)", height=420)
    fig.update_layout(hovermode="closest", showlegend=False, margin=dict(l=110, r=60, t=56, b=40))
    fig.update_xaxes(gridcolor=GRID, showgrid=True)
    fig.update_yaxes(gridcolor="rgba(0,0,0,0)")
    return fig


FIGS = {
    "overview": [("spend_claims", fig_spend_claims), ("concentration", fig_concentration)],
    "permember": [("pmpm_national", fig_pmpm_national), ("pmpm_bridge", fig_pmpm_bridge), ("enrollment_mix", fig_enrollment_mix)],
    "geography": [("state_ranked", fig_state_ranked), ("state_scatter", fig_state_scatter)],
    "negotiation": [("neg_exposure", fig_negotiation_exposure), ("negotiation", fig_negotiation)],
    "drivers": [("pvm_years", fig_pvm_years), ("unit_price", fig_unit_price)],
    "drugs": [("top_drugs", fig_top_drugs), ("movers", fig_movers), ("glp1", fig_glp1)],
    "market": [("manufacturers", fig_manufacturers)],
}

ABOUT = """
<div class="method">
<div class="warn"><b>Real public data.</b> CMS Medicare Part D Spending by Drug, from data.cms.gov: the annual file for 2020 to 2024 and the preliminary quarterly file for 2025. This is aggregate drug-level data for all of Medicare Part D, not any one plan and not claim-level.</div>
<h3>What the numbers are</h3>
<ul>
<li><b>Gross drug cost</b>: Medicare, plan and beneficiary payments for the claim. CMS does not publish rebates or other price concessions, so this is not net cost to a plan.</li>
<li><b>Per-member figures</b> divide the spending file by member months from CMS Monthly Enrollment (Part D enrollees summed over the 12 months). Spending and enrollment are separate CMS releases; they reconcile in the checks tab.</li>
<li><b>State view</b> uses the prescriber-by-geography file (cost by where the prescriber practices) over enrollees by state of residence. They differ a little, so treat state gaps as indicative.</li>
<li><b>Negotiated prices</b> are typed in from CMS's fact sheet (link below). Observed change is spend per claim in the preliminary Q1 2026 file against the 2025 file, so it is a check on direction and size, not a measurement of savings.</li>
<li><b>Trend breakdown</b> uses the same price/volume/mix algebra as the synthetic pipeline, with dose units as volume. Dose units mix tablets, millilitres and pens, so "mix" also absorbs unit differences; read it as a shift between drugs.</li>
<li>Drug rows are CMS's "Overall" rows (all manufacturers). The manufacturer view uses the per-manufacturer rows.</li>
</ul>
<h3>Cautions</h3>
<ul>
<li>2025 is from the quarterly file. CMS says it is preliminary, can change with claims lag, and should not be compared directly with the annual file. It is shown as a single number and left out of growth rates. Q1 2026 is not used.</li>
<li>Drugs are matched by brand and generic name; a drug that CMS renamed between years appears as an exit and an entry.</li>
<li>The 2024 and 2025 files are separate releases; their gap is not treated as a finding.</li>
</ul>
<p>Negotiated prices: <a href="https://cms.gov/files/document/fact-sheet-negotiated-prices-initial-price-applicability-year-2026.pdf">CMS fact sheet</a>. Also: <a href="https://data.cms.gov/summary-statistics-on-use-and-payments/medicare-medicaid-enrollment/medicare-monthly-enrollment">Medicare Monthly Enrollment</a>, <a href="https://data.cms.gov/provider-summary-by-type-of-service/medicare-part-d-prescribers/medicare-part-d-prescribers-by-geography-and-drug">Part D Prescribers by Geography and Drug</a>.</p>
<p>Source: <a href="https://data.cms.gov/summary-statistics-on-use-and-payments/medicare-medicaid-spending-by-drug/medicare-part-d-spending-by-drug">Medicare Part D Spending by Drug</a>, <a href="https://data.cms.gov/summary-statistics-on-use-and-payments/medicare-medicaid-spending-by-drug/medicare-quarterly-part-d-spending-by-drug">Medicare Quarterly Part D Spending by Drug</a>.</p>
</div>
"""


def _table(fig: go.Figure) -> str:
    frames = []
    for tr in fig.data:
        x, y = getattr(tr, "x", None), getattr(tr, "y", None)
        if x is not None and y is not None and len(x) == len(y) and len(y):
            frames.append(pd.DataFrame({"series": tr.name or "", "x": [str(v)[:40] for v in x], "y": list(y)}))
    if not frames:
        return ""
    return "<details><summary>View data</summary>" + pd.concat(frames).head(80).to_html(index=False, border=0, float_format=lambda v: f"{v:,.3f}") + "</details>"


GEO_NOTE = ("<div class='warn' style='margin:0 0 12px'>Read with care: cost is attributed to where the <b>prescriber</b> practices, enrollment to where the member lives. "
            "Washington DC at about $840 is almost certainly inflated by prescribers there treating members who live in Maryland and Virginia. "
            "Territories are excluded for the same reason. Differences between states mix use, price, drug mix, plan type and income-subsidy share; this view does not separate them.</div>")

NEG_NOTE = ("<div class='warn' style='margin:0 0 12px'>The announced cut compares the negotiated price (MFP) with the list price CMS published. The data shows spend per claim, which also moves with strength and pack mix, "
            "and Q1 2026 is preliminary. NovoLog's list price was cut about 75% in 2024, so little of the announced 76% is left to show between 2025 and 2026. "
            "Entresto and Januvia differ from the announced cut in ways I have not explained. This checks direction and size; it is not a savings measurement.</div>")


def neg_table_html(d: dict) -> str:
    n = d["negotiation"].sort_values("spend_2024", ascending=False)
    rows = "".join(
        f"<tr><td style='text-align:left'>{html.escape(r.drug)}</td><td>${r.list_price_30d:,.0f}</td><td>${r.mfp_30d:,.0f}</td><td>{r.mfp_discount:.0%}</td>"
        f"<td>${r.spend_2024/1e9:,.2f}B</td><td>${r.implied_gross_reduction_2024_volume/1e9:,.2f}B</td><td>{r.observed_change_per_claim:+.0%}</td></tr>"
        for r in n.itertuples())
    tot = n["spend_2024"].sum(); red = n["implied_gross_reduction_2024_volume"].sum()
    mm = d["natl"].set_index("year").loc[2024, "member_months"]
    return ("<div class='card' style='padding:16px'><h3 style='margin-top:0'>Exposure arithmetic (illustrative)</h3>"
            "<table style='display:table'><tr><th style='text-align:left'>Drug</th><th>List, 30 days</th><th>Negotiated, 30 days</th><th>Cut</th><th>2024 gross spend</th><th>Cut applied to 2024 spend</th><th>Spend per claim, Q1 2026 vs 2025</th></tr>"
            + rows + f"<tr><td style='text-align:left'><b>Total</b></td><td></td><td></td><td></td><td><b>${tot/1e9:,.1f}B</b></td><td><b>${red/1e9:,.1f}B</b></td><td></td></tr></table>"
            f"<p style='color:#52514e'>At constant 2024 volume and ignoring rebates, the cuts would take about ${red/1e9:,.0f}B ({red/tot:.0%} of these drugs' spend, "
            f"{red/d['totals'].set_index('year').loc[2024,'spend']:.0%} of all 2024 gross Part D spend), or about ${red/mm:,.0f} per member per month. "
            "It is a ceiling for a gross view: plans and manufacturers already paid rebates on these drugs, so the net effect for a plan is smaller. Not a forecast.</p></div>")


def quality_html(d: dict) -> str:
    rows = "".join(
        f"<tr><td style='text-align:left'>{html.escape(c['check'])}</td><td>{c['a']:,.0f}</td><td>{c['b']:,.0f}</td><td>{c['diff_pct']:+.3%}</td><td>{'pass' if c['pass'] else 'FAIL'}</td></tr>"
        for c in d["recon"])
    return ("<div class='card' style='padding:16px'><h3 style='margin-top:0'>Cross-file checks (run on every build)</h3>"
            "<table style='display:table'><tr><th style='text-align:left'>Check</th><th>A</th><th>B</th><th>Difference</th><th>Result</th></tr>" + rows + "</table>"
            "<p style='color:#52514e'>Enrollment, spending and prescriber files come from different CMS releases. A difference under the tolerance means they describe the same program; "
            "a larger one would be investigated before any number is published. Territories are left out of the state comparison because prescriber location and beneficiary residence differ too much there.</p></div>")


def build() -> str:
    d = build_data()
    k, ins = kpis(d)
    tiles = [
        ("2024 gross spend", f"${k['spend_2024']/1e9:,.0f}B", f"{k['cagr']:.1%} a year since 2020"),
        ("2024 claims", f"{k['claims_2024']/1e9:,.2f}B", f"{k['claims_cagr']:.1%} a year since 2020"),
        ("Largest drug", k["top_drug"], f"${k['top_drug_spend']/1e9:,.1f}B in 2024"),
        ("Top 10 drug share", f"{k['top10_share']:.0%}", "of 2024 spend"),
        ("GLP-1 spend 2024", f"${k['glp1_2024']/1e9:,.1f}B", f"from ${k['glp1_2020']/1e9:,.1f}B in 2020"),
        ("Gross PMPM 2024", f"${k['pmpm_2024']:,.0f}", f"from ${k['pmpm_2020']:,.0f} in 2020"),
        ("Negotiated-2026 drugs", f"{k['neg_share']:.0%}", f"${k['neg_spend']/1e9:,.0f}B of 2024 spend"),
        ("2025 (preliminary)", f"${k['spend_2025_prelim']/1e9:,.0f}B", "quarterly file, not comparable"),
    ]
    tile_html = "".join(f'<div class="tile"><div class="l">{a}</div><div class="v">{html.escape(b)}</div><div class="s">{c}</div></div>' for a, b, c in tiles)
    tabs = [("overview", "Overview"), ("permember", "Per member"), ("drivers", "What drove spend"), ("drugs", "Drugs"),
            ("geography", "Geography"), ("negotiation", "2026 negotiation"), ("market", "Market structure")]
    panels = []
    for tid, _ in tabs:
        cards = []
        if tid == "geography":
            cards.append(GEO_NOTE)
        if tid == "negotiation":
            cards.append(NEG_NOTE)
        for _, fn in FIGS[tid]:
            fig = fn(d)
            cards.append(f'<div class="card">{fig.to_html(full_html=False, include_plotlyjs=False, config={"displaylogo": False})}{_table(fig)}</div>')
        if tid == "negotiation":
            cards.append(neg_table_html(d))
        panels.append(f'<section class="panel" id="{tid}">{"".join(cards)}</section>')
    panels.append(f'<section class="panel" id="quality">{quality_html(d)}</section>')
    panels.append(f'<section class="panel" id="method">{ABOUT}</section>')
    nav = "".join(f'<button data-t="{t}" aria-selected="false">{n}</button>' for t, n in tabs) + '<button data-t="quality" aria-selected="false">Data checks</button><button data-t="method" aria-selected="false">About the data</button>'
    ins_html = "<ul>" + "".join(f"<li>{html.escape(i)}</li>" for i in ins) + "</ul>"
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>Medicare Part D Spending Trends</title><style>{CSS}</style><script>{get_plotlyjs()}</script></head><body>"
        "<header><h1>Medicare Part D Spending Trends, 2020 to 2024</h1>"
        "<p>Real CMS public data: gross drug spending by drug across all of Part D. Not UnitedHealth Group data and not net of rebates.</p></header>"
        f"<main><div class='tiles'>{tile_html}</div><div class='insights'>{ins_html}</div><nav>{nav}</nav>{''.join(panels)}</main>"
        f"<script>{JS}</script></body></html>"
    )


def run() -> str:
    fetch()
    config.REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = config.REPORT_DIR / "partd_public_cms_dashboard.html"
    out.write_text(build(), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size/1e6:.1f} MB)")
    return str(out)


if __name__ == "__main__":
    run()
