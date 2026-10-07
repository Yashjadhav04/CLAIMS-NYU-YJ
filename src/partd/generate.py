"""Generate a synthetic Part D prescription-drug-event (PDE) data set.

The data is entirely synthetic (no real members, prices or plan data). It is built so the downstream analytics
face the same problems a real Part D actuarial analyst does:

* PDE submission records with originals, adjustments ('A'), deletions ('D') and rejected submissions with edit
  codes, so "final action" logic is required to get to a clean claim table
* claims arriving with a submission lag (a heavy tail), so the most recent months are incomplete (IBNR)
* a benefit design change between 2024 (legacy, with a coverage gap) and 2025+ (out-of-pocket cap + manufacturer
  discount program)
* a GLP-1 utilization ramp, annual brand price increases, a specialty tier, and a low-income subsidy (LIS) segment
* an operational incident: a spike in edit 705 rejections for March 2026 fills
* a deliberately imperfect synthetic budget (bid) so that actual-versus-budget variance is non-trivial

Run:  PYTHONPATH=src python -m partd.generate
"""
from __future__ import annotations

import json
from datetime import timedelta

import numpy as np
import pandas as pd

from . import config
from .benefit import BenefitState, adjudicate, load_designs, load_tier_rates
from .drugs import ANNUAL_STOP_HAZARD, SHARE_90_DAY, build_drug_reference

STATES = ["MN", "WI", "FL", "TX", "CA", "AZ", "NY", "OH", "PA", "IL"]
STATE_P = [0.16, 0.10, 0.14, 0.13, 0.12, 0.07, 0.09, 0.07, 0.07, 0.05]

PLANS = [
    ("S5001-001", "S5001", "PDP", "Value Rx PDP"),
    ("S5001-002", "S5001", "PDP", "Premier Rx PDP"),
    ("H1001-001", "H1001", "MAPD", "Choice MAPD"),
    ("H1001-002", "H1001", "MAPD", "Plus MAPD"),
]

EDIT_CODES = ["705", "715", "738", "999"]
EDIT_P = [0.40, 0.20, 0.30, 0.10]
INCIDENT_MONTH = pd.Timestamp("2026-03-01")  # spike in 705 (no Part D enrollment on file) for March fills


def _month_table() -> tuple[pd.DatetimeIndex, np.ndarray, np.ndarray, int]:
    start = pd.Timestamp(config.START_DATE)
    end = pd.Timestamp(config.END_DATE)
    months = pd.date_range(start.replace(day=1), end, freq="MS")
    mstart = (months - start).days.values.astype(int)
    next_start = np.append(mstart[1:], (end - start).days + 1)
    mend = next_start - 1
    return months, mstart, mend, int((end - start).days + 1)


def _make_members(rng: np.random.Generator, n: int, n_months: int):
    ids = np.array([f"M{i:07d}" for i in range(1, n + 1)])
    disabled = rng.random(n) < 0.09
    age = np.where(disabled, rng.integers(45, 65, n), np.clip(rng.normal(74, 7.5, n), 65, 99)).astype(int)
    sex = np.where(rng.random(n) < 0.56, "F", "M")
    state = rng.choice(STATES, n, p=STATE_P)
    mapd = rng.random(n) < 0.45
    plan_choice = rng.integers(0, 2, n) + np.where(mapd, 2, 0)
    lis = rng.random(n) < np.where(mapd, 0.30, 0.20)
    z = rng.normal(0, 1, n)  # latent morbidity
    risk = np.exp(0.28 * z + 0.012 * (age - 74))
    ltc = rng.random(n) < np.where(age >= 85, 0.12, 0.02)

    initial = rng.random(n) < 0.73
    start_m = np.where(initial, 0, rng.integers(1, n_months - 1, n))
    end_m = np.minimum(start_m + rng.geometric(0.006, n) - 1, n_months - 1)

    members = pd.DataFrame(
        {
            "member_id": ids,
            "birth_year": 2026 - age,
            "sex": sex,
            "state": state,
            "risk_score": np.round(risk, 3),
            "ltc_flag": ltc,
            "is_disabled_entitlement": disabled,
        }
    )
    return members, plan_choice, lis, z, age, ltc, start_m, end_m


def _price_index(is_generic: np.ndarray, year: np.ndarray, month: np.ndarray, months_since_start: np.ndarray):
    brand = (1.05 ** (year - 2024)) * np.where(month >= 7, 1.01, 1.0)
    generic = 0.9985**months_since_start
    return np.where(is_generic, generic, brand)


def generate(n_members: int | None = None, seed: int | None = None, verbose: bool = True) -> dict:
    n_members = n_members or config.N_MEMBERS
    rng = np.random.default_rng(seed if seed is not None else config.RNG_SEED)
    months, mstart_day, mend_day, n_days = _month_table()
    n_months = len(months)
    start_ts = pd.Timestamp(config.START_DATE)
    as_of = pd.Timestamp(config.AS_OF_DATE)

    # ------------------------------------------------------------------ members, plans, enrollment
    members, plan_choice, lis, z, age, ltc, start_m, end_m = _make_members(rng, n_members, n_months)
    plan_ids = np.array([p[0] for p in PLANS])[plan_choice]
    members["plan_id"] = plan_ids
    members["lis_flag"] = lis
    plans = pd.DataFrame(PLANS, columns=["plan_id", "contract_id", "plan_type", "plan_name"])

    enr_rows = []
    for i in range(n_members):
        ms = months[start_m[i] : end_m[i] + 1]
        enr_rows.append(
            pd.DataFrame(
                {
                    "member_id": members.member_id.values[i],
                    "month_start": ms,
                    "plan_id": plan_ids[i],
                    "lis_flag": bool(lis[i]),
                }
            )
        )
    enrollment = pd.concat(enr_rows, ignore_index=True)
    enrollment["month_start"] = enrollment["month_start"].dt.date

    # ------------------------------------------------------------------ pharmacies
    types = (
        ["Retail chain"] * 400 + ["Independent"] * 100 + ["Mail order"] * 30 + ["Specialty"] * 30 + ["LTC"] * 40
    )
    pharm = pd.DataFrame(
        {
            "pharmacy_id": [f"PH{i:04d}" for i in range(1, len(types) + 1)],
            "pharmacy_npi": [f"9{x:09d}" for x in rng.integers(0, 10**9, len(types))],
            "pharmacy_type": types,
            "state": rng.choice(STATES, len(types), p=STATE_P),
        }
    )
    ptype = pharm.pharmacy_type.values
    retail_ids = np.where(np.isin(ptype, ["Retail chain", "Independent"]))[0]
    mail_ids = np.where(ptype == "Mail order")[0]
    spec_ids = np.where(ptype == "Specialty")[0]
    ltc_ids = np.where(ptype == "LTC")[0]
    retail_pref = rng.choice(retail_ids, size=(n_members, 3))

    # ------------------------------------------------------------------ therapies (member x drug)
    drugs = build_drug_reference()
    nd = len(drugs)
    kind = drugs["kind"].values
    prev = drugs["prevalence"].values
    mult = np.where(kind == "generic", 1.25, np.where(kind == "specialty", 1.45, 1.55))
    age_f = 1 + 0.012 * (age - 74)
    P = np.clip(prev[None, :] * mult[None, :] * np.exp(0.35 * z)[:, None] * age_f[:, None], 0, 0.9)
    mi, di = np.nonzero(rng.random(P.shape) < P)
    npair = len(mi)

    w0 = mstart_day[start_m[mi]]
    w1 = mend_day[end_m[mi]]
    launch = np.maximum((pd.to_datetime(drugs["launch_date"]) - start_ts).dt.days.values, 0)[di]
    is_growth = kind[di] == "growth"
    ds_all = np.where(rng.random(npair) < pd.Series(kind[di]).map(SHARE_90_DAY).values, 90, 30)
    ongoing = rng.random(npair) < np.where(is_growth, 0.10, 0.88)
    u = np.where(is_growth, rng.beta(2.6, 1.0, npair), rng.random(npair))
    # Therapies already underway at the start of a member's enrollment get their first fill at a random point in one
    # refill cycle; without this, every 90-day therapy refills in the same month and PMPM zigzags quarterly.
    ongoing_offset = (rng.random(npair) * ds_all).astype(int)
    start = np.where(ongoing, np.maximum(w0, launch) + ongoing_offset, w0 + (w1 - w0) * u)
    start = np.maximum(start, launch).astype(int)
    hazard = pd.Series(kind[di]).map(ANNUAL_STOP_HAZARD).values.astype(float)
    end = np.minimum(start + rng.exponential(365.0 / hazard), w1).astype(int)
    keep = start <= end
    mi, di, start, end, ds_pair = mi[keep], di[keep], start[keep], end[keep], ds_all[keep]
    npair = len(mi)

    pair_chunks, day_chunks = [], []
    for k in range(npair):
        span = end[k] - start[k]
        m = int(span // ds_pair[k]) + 2
        gaps = rng.poisson(1.5, m) + (rng.random(m) < 0.08) * rng.integers(7, 35, m)
        steps = ds_pair[k] + gaps
        steps[0] = 0
        days = start[k] + np.cumsum(steps)
        days = days[days <= end[k]]
        if len(days):
            pair_chunks.append(np.full(len(days), k, dtype=np.int32))
            day_chunks.append(days.astype(np.int32))
    pair_idx = np.concatenate(pair_chunks)
    fill_day = np.concatenate(day_chunks)

    c_member = mi[pair_idx]
    c_drug = di[pair_idx]
    c_ds = ds_pair[pair_idx]
    order = np.lexsort((c_drug, fill_day, c_member))
    c_member, c_drug, c_ds, fill_day = c_member[order], c_drug[order], c_ds[order], fill_day[order]
    n = len(c_member)

    fill_ts = start_ts + pd.to_timedelta(fill_day, unit="D")
    year = fill_ts.year.values
    month = fill_ts.month.values
    msince = (year - 2024) * 12 + month - 1

    # ------------------------------------------------------------------ pharmacy assignment
    ph = retail_pref[c_member, rng.integers(0, 3, n)]
    is_spec = kind[c_drug] == "specialty"
    mail_mask = (c_ds == 90) & (rng.random(n) < 0.60)
    ph = np.where(mail_mask, mail_ids[rng.integers(0, len(mail_ids), n)], ph)
    ph = np.where(is_spec, spec_ids[rng.integers(0, len(spec_ids), n)], ph)
    ph = np.where(ltc[c_member], ltc_ids[rng.integers(0, len(ltc_ids), n)], ph)
    c_ptype = ptype[ph]

    # ------------------------------------------------------------------ cost build-up
    is_gen = drugs["is_generic"].values[c_drug]
    price30 = drugs["price_per_30_days"].values[c_drug]
    pidx = _price_index(is_gen, year, month, msince)
    sigma = np.where(is_gen, 0.30, np.where(is_spec, 0.01, 0.015))
    noise = np.clip(np.exp(rng.normal(0, sigma)), 0.4, 3.0)
    ingredient = np.round(price30 * (c_ds / 30.0) * pidx * noise, 2)
    fee_mean = pd.Series(c_ptype).map(
        {"Retail chain": 1.4, "Independent": 2.1, "Mail order": 0.4, "Specialty": 3.5, "LTC": 2.0}
    ).values
    fee = np.round(np.clip(rng.normal(fee_mean, 0.3), 0.0, None), 2)
    gross = np.round(ingredient + fee, 2)
    qty = drugs["units_per_day"].values[c_drug] * c_ds

    # ------------------------------------------------------------------ benefit engine (sequential per member-year)
    designs = load_designs()
    tier_rates = load_tier_rates()
    tier_rate = np.array([tier_rates[int(t)] for t in drugs["tier"].values])
    applicable = ~drugs["is_generic"].values
    generic_flag = drugs["is_generic"].values

    gdcb = np.zeros(n)
    gdca = np.zeros(n)
    pay = np.zeros(n)
    lics_a = np.zeros(n)
    cpp = np.zeros(n)
    mfr = np.zeros(n)
    state_map: dict[tuple[int, int], BenefitState] = {}
    for i in range(n):
        key = (int(c_member[i]), int(year[i]))
        s = state_map.get(key)
        if s is None:
            s = BenefitState()
            state_map[key] = s
        d = int(c_drug[i])
        sp = adjudicate(designs[int(year[i])], s, float(gross[i]), tier_rate[d], bool(applicable[d]),
                        bool(lis[c_member[i]]), bool(generic_flag[d]))
        gdcb[i], gdca[i], pay[i], lics_a[i], cpp[i], mfr[i] = sp.gdcb, sp.gdca, sp.patient_pay, sp.lics, sp.cpp, sp.mfr_discount

    claims = pd.DataFrame(
        {
            "claim_group_id": [f"RX{i:09d}" for i in range(1, n + 1)],
            "member_id": members.member_id.values[c_member],
            "drug_id": drugs.drug_id.values[c_drug],
            "pharmacy_id": pharm.pharmacy_id.values[ph],
            "fill_date": fill_ts.date,
            "days_supply": c_ds.astype(int),
            "quantity_dispensed": qty.astype(float),
            "ingredient_cost": ingredient,
            "dispensing_fee": fee,
            "gdcb": gdcb,
            "gdca": gdca,
            "patient_pay_amt": pay,
            "lics_amt": lics_a,
            "cpp_amt": cpp,
            "mfr_discount_amt": mfr,
        }
    )

    # ------------------------------------------------------------------ PDE submission records
    fill_dt = pd.to_datetime(claims["fill_date"])
    lag = np.where(rng.random(n) < 0.92, np.minimum(1 + rng.gamma(1.2, 4.0, n), 45), rng.uniform(20, 90, n)).astype(int)
    received = fill_dt + pd.to_timedelta(lag, unit="D")

    fill_month = fill_dt.dt.to_period("M").dt.to_timestamp()
    incident = (fill_month == INCIDENT_MONTH).values
    reject = rng.random(n) < np.where(incident, 0.085, 0.020)
    code = rng.choice(EDIT_CODES, n, p=EDIT_P)
    code = np.where(incident & (rng.random(n) < 0.80), "705", code)
    resolved = rng.random(n) < np.where(incident, 0.97, 0.95)
    delay = np.where(
        incident,
        14 + rng.gamma(2.0, 10.0, n),  # file fix landed in April; resubmissions trickled in over several weeks
        1 + rng.gamma(2.0, 5.0, n),
    ).astype(int)

    base_cols = [c for c in claims.columns]
    acc_first = claims.copy()
    acc_first["adjustment_deletion_code"] = ""
    acc_first["dcs_status"] = "A"
    acc_first["edit_code"] = ""
    acc_first["received_date"] = np.where(reject, received + pd.to_timedelta(delay, unit="D"), received)

    rej = claims[reject].copy()
    rej["adjustment_deletion_code"] = ""
    rej["dcs_status"] = "R"
    rej["edit_code"] = code[reject]
    rej["received_date"] = received[reject]

    acc_first = acc_first[~(reject & ~resolved)]  # unresolved rejections never get an accepted record

    # adjustments: price corrections on plan-only catastrophic claims (does not disturb cumulative TrOOP)
    elig = (year >= 2025) & (pay == 0) & (lics_a == 0) & (gdcb == 0) & (gross > 0)
    adj_mask = elig & (rng.random(n) < 0.10) & ~reject
    adj = claims[adj_mask].copy()
    f = rng.uniform(0.90, 0.99, adj_mask.sum())
    new_gross = np.round(adj["gdca"].values * f, 2)
    new_mfr = np.round(adj["mfr_discount_amt"].values * f, 2)
    adj["dispensing_fee"] = adj["dispensing_fee"].values
    adj["ingredient_cost"] = np.round(new_gross - adj["dispensing_fee"].values, 2)
    adj["gdca"] = new_gross
    adj["gdcb"] = 0.0
    adj["mfr_discount_amt"] = new_mfr
    adj["cpp_amt"] = np.round(new_gross - new_mfr, 2)
    adj["adjustment_deletion_code"] = "A"
    adj["dcs_status"] = "A"
    adj["edit_code"] = ""
    adj["received_date"] = acc_first.loc[adj.index, "received_date"].values + pd.to_timedelta(
        5 + rng.gamma(2.0, 8.0, len(adj)), unit="D"
    ).astype("timedelta64[ns]")
    adj["received_date"] = pd.to_datetime(adj["received_date"]).dt.normalize()

    # duplicate submissions (pharmacy double-billed) that are deleted later; only old enough to be cleaned up by as-of
    old = (as_of - fill_dt).dt.days.values > 75
    dup_mask = old & ~reject & (rng.random(n) < 0.006)
    dup = claims[dup_mask].copy()
    dup["claim_group_id"] = [f"RXD{i:08d}" for i in range(1, len(dup) + 1)]
    dup_first = dup.copy()
    dup_first["adjustment_deletion_code"] = ""
    dup_first["dcs_status"] = "A"
    dup_first["edit_code"] = ""
    dup_first["received_date"] = received[dup_mask].values + pd.to_timedelta(rng.integers(0, 3, len(dup)), unit="D")
    dup_del = dup_first.copy()
    dup_del["adjustment_deletion_code"] = "D"
    dup_del["received_date"] = dup_first["received_date"].values + pd.to_timedelta(
        3 + rng.gamma(2.0, 4.0, len(dup)), unit="D"
    ).astype("timedelta64[ns]")
    dup_del["received_date"] = pd.to_datetime(dup_del["received_date"]).dt.normalize()

    sub = pd.concat([acc_first, rej, adj, dup_first, dup_del], ignore_index=True)
    sub["received_date"] = pd.to_datetime(sub["received_date"]).dt.normalize()
    sub = sub[sub["received_date"] <= as_of].copy()  # only what has actually been received by the extract date
    sub = sub.sort_values(["received_date", "claim_group_id", "dcs_status"], kind="stable").reset_index(drop=True)
    sub.insert(0, "pde_id", [f"PDE{i:010d}" for i in range(1, len(sub) + 1)])
    sub["received_date"] = sub["received_date"].dt.date
    sub = sub[
        ["pde_id", "claim_group_id", "member_id", "drug_id", "pharmacy_id", "fill_date", "days_supply",
         "quantity_dispensed", "ingredient_cost", "dispensing_fee", "gdcb", "gdca", "patient_pay_amt", "lics_amt",
         "cpp_amt", "mfr_discount_amt", "adjustment_deletion_code", "dcs_status", "edit_code", "received_date"]
    ]

    # ------------------------------------------------------------------ synthetic budget (bid) seed
    mm = enrollment.groupby("month_start").size()
    mm.index = pd.to_datetime(mm.index)
    reins = np.array(
        [
            gdca[i] * (designs[int(year[i])].reins_applicable if applicable[c_drug[i]] else designs[int(year[i])].reins_nonapplicable)
            for i in range(n)
        ]
    )
    net_plan = cpp - reins
    by_month = pd.Series(net_plan).groupby(fill_month.values).sum()
    actual_pmpm = (by_month / mm.reindex(by_month.index)).sort_index()
    budget_rows = []
    for m in pd.date_range("2025-01-01", "2026-12-01", freq="MS"):
        if m.year == 2025:
            budget = actual_pmpm.loc[m] * (1 + float(np.clip(rng.normal(0.0, 0.02), -0.04, 0.04)))
        else:
            budget = actual_pmpm.loc[m - pd.DateOffset(years=1)] * (1 + config.BUDGET_TREND)
        budget_rows.append({"month_start": m.date(), "budget_net_plan_pmpm": round(float(budget), 2)})
    budget_df = pd.DataFrame(budget_rows)

    # ------------------------------------------------------------------ write
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    config.SEEDS_DIR.mkdir(parents=True, exist_ok=True)
    members.to_parquet(config.RAW_DIR / "members.parquet", index=False)
    plans.to_csv(config.RAW_DIR / "plans.csv", index=False)
    enrollment.to_parquet(config.RAW_DIR / "enrollment_monthly.parquet", index=False)
    pharm.to_parquet(config.RAW_DIR / "pharmacies.parquet", index=False)
    drug_out = drugs.drop(columns=["prevalence"])
    drug_out.to_parquet(config.RAW_DIR / "drugs.parquet", index=False)
    sub.to_parquet(config.RAW_DIR / "pde_submissions.parquet", index=False)
    budget_df.to_csv(config.SEEDS_DIR / "budget_net_plan_pmpm.csv", index=False)

    summary = {
        "members_ever_enrolled": int(n_members),
        "member_months": int(len(enrollment)),
        "true_claims": int(n),
        "pde_submission_rows": int(len(sub)),
        "gross_pmpm_by_year": {
            int(y): round(float(gross[year == y].sum() / mm[mm.index.year == y].sum()), 2) for y in (2024, 2025, 2026)
        },
        "net_plan_pmpm_by_year": {
            int(y): round(float(net_plan[year == y].sum() / mm[mm.index.year == y].sum()), 2) for y in (2024, 2025, 2026)
        },
        "claims_per_member_month": round(n / len(enrollment), 2),
        "specialty_share_of_gross": round(float(gross[is_spec].sum() / gross.sum()), 3),
        "glp1_share_of_gross_2026": round(
            float(gross[(year == 2026) & np.isin(kind[c_drug], ["growth"])].sum() / gross[year == 2026].sum()), 3
        ),
        "rejected_submissions": int((sub["dcs_status"] == "R").sum()),
        "adjustment_records": int((sub["adjustment_deletion_code"] == "A").sum()),
        "deletion_records": int((sub["adjustment_deletion_code"] == "D").sum()),
    }
    (config.RAW_DIR / "_generation_summary.json").write_text(json.dumps(summary, indent=2))
    if verbose:
        print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    generate()
