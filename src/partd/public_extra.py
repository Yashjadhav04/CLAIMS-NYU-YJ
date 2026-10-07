"""More real public data for the Part D analysis, and the analyst-style work on top of it.

Sources (all data.cms.gov):
  * Medicare Monthly Enrollment: monthly Part D enrollees nationally and by state, split PDP / MA-PD and by low-income subsidy.
    This supplies the member months the spending file lacks, so gross cost can be shown per member per month.
  * Medicare Part D Prescribers by Geography and Drug (2024): state-level drug cost, used to compare states and to reconcile
    against the national spending file.
  * Medicare Quarterly Part D Spending by Drug: Q1 2026 spend per claim, used to check the first Medicare negotiated prices.
  * src/partd/mfp_2026.csv: the ten negotiated prices for 2026, transcribed from the CMS fact sheet (source URL in the file's docs).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from . import config

PUBLIC_DIR = config.DATA_DIR / "public"
ENROLL = PUBLIC_DIR / "cms_monthly_enrollment.csv"
GEO = PUBLIC_DIR / "cms_geo_drug_latest.csv"
QUARTERLY = PUBLIC_DIR / "cms_partd_spending_by_drug_quarterly.csv"
ANNUAL = PUBLIC_DIR / "cms_partd_spending_by_drug_annual.csv"
MFP = Path(__file__).with_name("mfp_2026.csv")
STATES_DC = set("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split())
MFP_SOURCE = "https://cms.gov/files/document/fact-sheet-negotiated-prices-initial-price-applicability-year-2026.pdf"
YEARS = [2020, 2021, 2022, 2023, 2024]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
ENROLL_COLS = ["PRSCRPTN_DRUG_TOT_BENES", "PRSCRPTN_DRUG_PDP_BENES", "PRSCRPTN_DRUG_MAPD_BENES",
               "PRSCRPTN_DRUG_DEEMED_ELIGIBLE_FULL_LIS_BENES", "PRSCRPTN_DRUG_FULL_LIS_BENES",
               "PRSCRPTN_DRUG_PARTIAL_LIS_BENES", "PRSCRPTN_DRUG_NO_LIS_BENES"]


# ----------------------------------------------------------------------------------------------- loaders
def load_enrollment() -> pd.DataFrame:
    e = pd.read_csv(ENROLL, low_memory=False, dtype=str)
    for c in ENROLL_COLS:
        e[c] = pd.to_numeric(e[c], errors="coerce")
    e["YEAR"] = e["YEAR"].astype(int)
    return e[e["MONTH"] != "Year"].copy()


def national_monthly(e: pd.DataFrame) -> pd.DataFrame:
    n = e[e["BENE_GEO_LVL"] == "National"].copy()
    n["month_num"] = n["MONTH"].map({m: i + 1 for i, m in enumerate(MONTHS)})
    n["date"] = pd.to_datetime(dict(year=n["YEAR"], month=n["month_num"], day=1))
    n = n.rename(columns={"PRSCRPTN_DRUG_TOT_BENES": "enrollees", "PRSCRPTN_DRUG_PDP_BENES": "pdp", "PRSCRPTN_DRUG_MAPD_BENES": "mapd"})
    n["lis"] = n["PRSCRPTN_DRUG_DEEMED_ELIGIBLE_FULL_LIS_BENES"].fillna(0) + n["PRSCRPTN_DRUG_FULL_LIS_BENES"].fillna(0) + n["PRSCRPTN_DRUG_PARTIAL_LIS_BENES"].fillna(0)
    return n[["date", "YEAR", "enrollees", "pdp", "mapd", "lis"]].sort_values("date").reset_index(drop=True)


def annual_member_months(nm: pd.DataFrame) -> pd.DataFrame:
    g = nm.groupby("YEAR").agg(member_months=("enrollees", "sum"), months=("enrollees", "size"), pdp_mm=("pdp", "sum"), mapd_mm=("mapd", "sum"), lis_mm=("lis", "sum"))
    g["avg_enrollees"] = g["member_months"] / g["months"]
    g["lis_share"] = g["lis_mm"] / g["member_months"]
    g["mapd_share"] = g["mapd_mm"] / g["member_months"]
    return g.reset_index().rename(columns={"YEAR": "year"})


def national_pmpm(totals: pd.DataFrame, mm: pd.DataFrame) -> pd.DataFrame:
    t = totals.merge(mm[["year", "member_months", "avg_enrollees", "lis_share", "mapd_share", "months"]], on="year")
    t = t[t["months"] == 12].copy()
    t["gross_pmpm"] = t["spend"] / t["member_months"]
    t["claims_per_1000_mm"] = t["claims"] / t["member_months"] * 1000
    t["spend_per_claim"] = t["spend"] / t["claims"]
    return t.reset_index(drop=True)


def pmpm_bridge(t: pd.DataFrame, y0: int, y1: int) -> dict:
    """gross PMPM = (claims per member month) x (spend per claim). Exact two-factor split (log-share allocation)."""
    a, b = t.set_index("year").loc[y0], t.set_index("year").loc[y1]
    d = b["gross_pmpm"] - a["gross_pmpm"]
    lf = np.log(b["claims_per_1000_mm"] / a["claims_per_1000_mm"])
    lp = np.log(b["spend_per_claim"] / a["spend_per_claim"])
    tot = lf + lp
    return {"from": y0, "to": y1, "pmpm_from": a["gross_pmpm"], "pmpm_to": b["gross_pmpm"], "change": d,
            "utilization": d * lf / tot if tot else 0.0, "cost_per_claim": d * lp / tot if tot else 0.0}


def load_geo() -> pd.DataFrame:
    g = pd.read_csv(GEO, low_memory=False, dtype={"Prscrbr_Geo_Cd": str})
    return g


def state_pmpm(e: pd.DataFrame, geo: pd.DataFrame, year: int = 2024) -> pd.DataFrame:
    s = e[(e["BENE_GEO_LVL"] == "State") & (e["YEAR"] == year)]
    mm = s.groupby(["BENE_STATE_ABRVTN", "BENE_STATE_DESC"])["PRSCRPTN_DRUG_TOT_BENES"].sum().reset_index()
    mm.columns = ["state", "state_name", "member_months"]
    g = geo[geo["Prscrbr_Geo_Lvl"] == "State"].groupby("Prscrbr_Geo_Desc").agg(
        spend=("Tot_Drug_Cst", "sum"), claims=("Tot_Clms", "sum"), fills30=("Tot_30day_Fills", "sum")).reset_index()
    m = mm.merge(g, left_on="state_name", right_on="Prscrbr_Geo_Desc", how="inner")
    m = m[m["state"].isin(STATES_DC)].copy()  # territories excluded: prescriber location vs beneficiary residence mismatch is too large
    m["gross_pmpm"] = m["spend"] / m["member_months"]
    m["fills_per_member_month"] = m["fills30"] / m["member_months"]
    m["cost_per_fill"] = m["spend"] / m["fills30"]
    return m.sort_values("gross_pmpm", ascending=False).reset_index(drop=True)


# ----------------------------------------------------------------------------------------------- negotiated prices
def negotiation_table() -> pd.DataFrame:
    m = pd.read_csv(MFP)
    m["discount"] = 1 - m["mfp_30d"] / m["list_price_30d"]
    ann = pd.read_csv(ANNUAL)
    ann = ann[ann["Mftr_Name"] == "Overall"]
    q = pd.read_csv(QUARTERLY, usecols=range(10))
    q = q[q["Mftr_Name"] == "Overall"]
    q25, q26 = q[q["Year"].str.startswith("2025")], q[q["Year"].str.startswith("2026")]
    rows = []
    for _, r in m.iterrows():
        pats = r["brand_prefixes"].split("|")

        def pick(df, col="Brnd_Name"):
            mask = pd.Series(False, index=df.index)
            for p in pats:
                mask |= df[col].str.lower().str.startswith(p.lower())
            if r["drug"] == "Fiasp/NovoLog":  # exclude NovoLog mixes, which were not selected
                mask &= ~df[col].str.lower().str.contains("mix")
            return df[mask]
        a, b, c = pick(ann), pick(q25), pick(q26)
        s24 = a["Tot_Spndng_2024"].sum()
        c24 = a["Tot_Clms_2024"].sum()
        pc25 = b["Tot_Spndng"].sum() / b["Tot_Clms"].sum() if len(b) else np.nan
        pc26 = c["Tot_Spndng"].sum() / c["Tot_Clms"].sum() if len(c) else np.nan
        rows.append({"drug": r["drug"], "list_price_30d": r["list_price_30d"], "mfp_30d": r["mfp_30d"], "mfp_discount": r["discount"],
                     "spend_2024": s24, "claims_2024": c24, "spend_per_claim_2024": s24 / c24 if c24 else np.nan,
                     "spend_per_claim_2025": pc25, "spend_per_claim_q1_2026": pc26,
                     "observed_change_per_claim": pc26 / pc25 - 1 if pc25 else np.nan,
                     "implied_gross_reduction_2024_volume": s24 * r["discount"]})
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------------------------- checks
def reconciliation(totals: pd.DataFrame, geo: pd.DataFrame, e: pd.DataFrame, overall: pd.DataFrame) -> list[dict]:
    """Automated cross-file checks; each returns pass/fail with the numbers, as an analyst would log them."""
    out = []
    spend24 = float(totals.set_index("year").loc[2024, "spend"])
    gn = float(geo.loc[geo["Prscrbr_Geo_Lvl"] == "National", "Tot_Drug_Cst"].sum())
    gs = float(geo.loc[geo["Prscrbr_Geo_Lvl"] == "State", "Tot_Drug_Cst"].sum())
    out.append({"check": "Spending-by-drug 2024 total vs prescriber-file national total", "a": spend24, "b": gn, "diff_pct": gn / spend24 - 1, "tolerance": 0.005})
    out.append({"check": "Prescriber-file national total vs sum of states", "a": gn, "b": gs, "diff_pct": gs / gn - 1, "tolerance": 0.01})
    nm = national_monthly(e)
    j = nm[nm["YEAR"] == 2024]
    out.append({"check": "Part D enrollees: PDP + MA-PD = total (Dec 2024)", "a": float(j.iloc[-1]["enrollees"]), "b": float(j.iloc[-1]["pdp"] + j.iloc[-1]["mapd"]),
                "diff_pct": float((j.iloc[-1]["pdp"] + j.iloc[-1]["mapd"]) / j.iloc[-1]["enrollees"] - 1), "tolerance": 0.001})
    ov = overall
    out.append({"check": "Drug rows with CMS outlier flag, 2024 (share of rows)", "a": float(ov["Outlier_Flag_2024"].sum()), "b": float(len(ov)),
                "diff_pct": float(ov["Outlier_Flag_2024"].sum() / len(ov)), "tolerance": None})
    out.append({"check": "Drug rows with spend but zero claims, 2024", "a": float(((ov["Tot_Spndng_2024"] > 0) & (ov["Tot_Clms_2024"].fillna(0) == 0)).sum()), "b": 0.0, "diff_pct": 0.0, "tolerance": 0})
    for c in out:
        c["pass"] = True if c["tolerance"] is None else abs(c["diff_pct"]) <= c["tolerance"] if c["tolerance"] else c["a"] == 0
    return out
