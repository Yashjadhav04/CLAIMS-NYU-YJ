"""Unit tests for the benefit engine: the money identity, the 2025+ out-of-pocket cap, phase straddling."""
import random

import pytest

from partd.benefit import BenefitState, adjudicate, load_designs, load_tier_rates

D = load_designs()
RATES = load_tier_rates()


def _run(year, claims, is_lis=False, applicable=True, generic=False, tier=3):
    d, s = D[year], BenefitState()
    out = []
    for g in claims:
        out.append(adjudicate(d, s, g, RATES[tier], applicable, is_lis, generic))
    return d, s, out


@pytest.mark.parametrize("year", [2024, 2025, 2026])
@pytest.mark.parametrize("is_lis", [False, True])
def test_money_identity_every_claim(year, is_lis):
    rng = random.Random(year)
    claims = [rng.choice([40, 300, 900, 2500, 7000]) * rng.uniform(0.5, 1.5) for _ in range(120)]
    _, _, out = _run(year, claims, is_lis=is_lis)
    for g, c in zip(claims, out):
        assert abs(g - (c.patient_pay + c.lics + c.cpp + c.mfr_discount)) < 0.011
        assert abs(g - (c.gdcb + c.gdca)) < 0.011


@pytest.mark.parametrize("year", [2025, 2026])
def test_ira_cap_member_never_exceeds_threshold(year):
    d, s, out = _run(year, [1500.0] * 80)
    assert sum(c.patient_pay for c in out) <= d.troop_threshold + 0.05


def test_catastrophic_member_pays_nothing_under_ira():
    d, s, out = _run(2025, [1500.0] * 80)
    assert sum(c.gdca for c in out) > 0
    last = out[-1]
    assert last.patient_pay == 0 and last.gdcb == 0


def test_deductible_phase_plan_pays_nothing_first_claim():
    d, s, out = _run(2025, [100.0])
    assert out[0].cpp == 0 and out[0].patient_pay == pytest.approx(100.0)


def test_straddling_claim_is_split_across_phases():
    d, s, out = _run(2025, [d_ := 1000.0])  # crosses the deductible
    assert out[0].patient_pay < 1000.0
    assert out[0].cpp > 0


def test_nonnegative_amounts():
    _, _, out = _run(2024, [250.0] * 200)
    for c in out:
        assert min(c.patient_pay, c.lics, c.cpp, c.mfr_discount, c.gdcb, c.gdca) >= -1e-9
