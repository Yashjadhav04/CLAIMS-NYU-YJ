-- 2025+ design: once derived TrOOP has reached the cap, a claim must carry no member or LIS cost share.
select claim_group_id, member_id, patient_pay_amt, lics_amt
from {{ claims_with_complete_history() }}
where benefit_design = 'ira'
  and benefit_phase_at_start = 'CATASTROPHIC'
  and patient_pay_amt + lics_amt > 0.30  -- tolerance mirrors the $0.25 TrOOP rounding tolerance in fct_pde_claims
