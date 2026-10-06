"""Simplified Medicare Part D benefit engine.

This is the *claim adjudication* logic used to generate synthetic PDE data. It is deliberately a simplified,
transparent model of the benefit, not a CMS-exact calculation:

* 2024 ("legacy" design): deductible -> initial coverage -> coverage gap -> catastrophic, with TrOOP counting the
  manufacturer gap discount.
* 2025+ ("ira" design): deductible -> initial coverage -> catastrophic, a hard annual out-of-pocket cap, and a
  manufacturer discount program (10% in initial coverage, 20% in catastrophic, applicable drugs only).

All parameters live in dbt_project/seeds/benefit_params.csv (single source of truth shared with dbt) and are
illustrative. Verify against the CMS Rate Announcement before using them for anything real.

Money identity for every claim (checked by tests):
    gross = patient_pay + lics + cpp + mfr_discount
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from . import config

PHASE_DED = "DEDUCTIBLE"
PHASE_ICL = "INITIAL_COVERAGE"
PHASE_GAP = "COVERAGE_GAP"
PHASE_CAT = "CATASTROPHIC"

EPS = 1e-9
INF = float("inf")


@dataclass(frozen=True)
class BenefitDesign:
    benefit_year: int
    design: str  # "legacy" | "ira"
    deductible: float
    icl_limit: float  # total gross drug cost limit (legacy only; inf for ira)
    troop_threshold: float  # catastrophic begins once TrOOP reaches this
    lis_copay_generic: float
    lis_copay_brand: float
    mfr_disc_icl: float
    mfr_disc_gap: float
    mfr_disc_cat: float
    gap_member_share: float
    cat_member_share: float
    reins_applicable: float
    reins_nonapplicable: float


class BenefitState:
    """Running accumulators for one member in one benefit year."""

    __slots__ = ("cum_gross", "troop")

    def __init__(self) -> None:
        self.cum_gross = 0.0
        self.troop = 0.0


@dataclass(frozen=True)
class ClaimSplit:
    gdcb: float  # gross drug cost below the out-of-pocket threshold
    gdca: float  # gross drug cost above the out-of-pocket threshold (catastrophic)
    patient_pay: float
    lics: float  # low-income cost-sharing subsidy
    cpp: float  # covered plan paid (before CMS reinsurance is netted out)
    mfr_discount: float


def load_designs(path: Path | None = None) -> dict[int, BenefitDesign]:
    path = path or (config.SEEDS_DIR / "benefit_params.csv")
    df = pd.read_csv(path)
    out: dict[int, BenefitDesign] = {}
    for r in df.to_dict("records"):
        icl = r["icl_limit"]
        out[int(r["benefit_year"])] = BenefitDesign(
            benefit_year=int(r["benefit_year"]),
            design=str(r["design"]),
            deductible=float(r["deductible"]),
            icl_limit=INF if pd.isna(icl) else float(icl),
            troop_threshold=float(r["troop_threshold"]),
            lis_copay_generic=float(r["lis_copay_generic"]),
            lis_copay_brand=float(r["lis_copay_brand"]),
            mfr_disc_icl=float(r["mfr_disc_icl"]),
            mfr_disc_gap=float(r["mfr_disc_gap"]),
            mfr_disc_cat=float(r["mfr_disc_cat"]),
            gap_member_share=float(r["gap_member_share"]),
            cat_member_share=float(r["cat_member_share"]),
            reins_applicable=float(r["reins_applicable"]),
            reins_nonapplicable=float(r["reins_nonapplicable"]),
        )
    return out


def load_tier_rates(path: Path | None = None) -> dict[int, float]:
    path = path or (config.SEEDS_DIR / "tier_cost_share.csv")
    df = pd.read_csv(path)
    return {int(t): float(r) for t, r in zip(df["tier"], df["cost_share_rate"])}


def current_phase(d: BenefitDesign, s: BenefitState) -> str:
    if s.troop >= d.troop_threshold - EPS:
        return PHASE_CAT
    if s.cum_gross < d.deductible - EPS:
        return PHASE_DED
    if d.design == "legacy" and s.cum_gross >= d.icl_limit - EPS:
        return PHASE_GAP
    return PHASE_ICL


def _rates(d: BenefitDesign, phase: str, tier_rate: float, applicable: bool) -> tuple[float, float, float]:
    """Return (member share, manufacturer discount share, TrOOP accrual) per gross dollar in this phase."""
    if phase == PHASE_DED:
        return 1.0, 0.0, 1.0
    if phase == PHASE_ICL:
        mfr = d.mfr_disc_icl if applicable else 0.0
        # Legacy design: no discounts in the initial coverage phase. IRA design: the discount does not count to TrOOP.
        return tier_rate, mfr, tier_rate
    if phase == PHASE_GAP:
        mfr = d.mfr_disc_gap if applicable else 0.0
        return d.gap_member_share, mfr, d.gap_member_share + mfr  # legacy: discount counts to TrOOP
    mfr = d.mfr_disc_cat if applicable else 0.0
    return d.cat_member_share, mfr, d.cat_member_share


def _capacity(d: BenefitDesign, s: BenefitState, phase: str, troop_rate: float) -> float:
    """Gross dollars that can still be absorbed in this phase before the next phase begins."""
    if phase == PHASE_CAT:
        return INF
    to_cap = (d.troop_threshold - s.troop) / troop_rate if troop_rate > 0 else INF
    if phase == PHASE_DED:
        return min(d.deductible - s.cum_gross, to_cap)
    if phase == PHASE_ICL:
        to_icl = d.icl_limit - s.cum_gross if d.design == "legacy" else INF
        return min(to_cap, to_icl)
    return to_cap  # coverage gap


def adjudicate(
    d: BenefitDesign,
    s: BenefitState,
    gross: float,
    tier_rate: float,
    applicable: bool,
    is_lis: bool,
    is_generic: bool,
) -> ClaimSplit:
    """Adjudicate one claim, splitting it across benefit phases if it straddles a boundary. Mutates `s`."""
    remaining = gross
    member = mfr = gdca = 0.0
    while remaining > EPS:
        phase = current_phase(d, s)
        m_rate, f_rate, t_rate = _rates(d, phase, tier_rate, applicable)
        cap = _capacity(d, s, phase, t_rate)
        take = remaining if cap >= remaining else cap
        if take <= EPS:  # guard against floating point stalls exactly on a boundary
            take = min(remaining, 1e-6)
        s.cum_gross += take
        s.troop += t_rate * take
        member += m_rate * take
        mfr += f_rate * take
        if phase == PHASE_CAT:
            gdca += take
        remaining -= take

    gross_c = round(gross, 2)
    member_c = round(member, 2)
    mfr_c = round(mfr, 2)
    gdca_c = min(round(gdca, 2), gross_c)

    if is_lis:
        copay = d.lis_copay_generic if is_generic else d.lis_copay_brand
        patient_pay = min(member_c, copay)
    else:
        patient_pay = member_c
    lics = round(member_c - patient_pay, 2)
    cpp = round(gross_c - patient_pay - lics - mfr_c, 2)
    return ClaimSplit(
        gdcb=round(gross_c - gdca_c, 2),
        gdca=gdca_c,
        patient_pay=round(patient_pay, 2),
        lics=lics,
        cpp=cpp,
        mfr_discount=mfr_c,
    )


def reinsurance_estimate(d: BenefitDesign, gdca: float, applicable: bool) -> float:
    """CMS reinsurance estimate on catastrophic gross drug cost (matches the dbt model)."""
    rate = d.reins_applicable if applicable else d.reins_nonapplicable
    return gdca * rate
