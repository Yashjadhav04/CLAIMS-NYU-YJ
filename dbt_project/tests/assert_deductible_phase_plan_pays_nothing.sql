-- A claim that starts in the deductible and fits entirely inside the remaining deductible must have no plan payment and
-- no manufacturer discount (the member / LIS pays the full cost).
select claim_group_id, member_id, gross_drug_cost, deductible, cum_gross_before, cpp_amt, mfr_discount_amt
from {{ claims_with_complete_history() }}
where benefit_phase_at_start = 'DEDUCTIBLE'
  and gross_drug_cost <= deductible - cum_gross_before + 0.01
  and (cpp_amt > 0.011 or mfr_discount_amt > 0.011)
