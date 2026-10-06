-- Every claim must satisfy: gross = patient pay + LICS + covered plan paid + manufacturer discount (to the cent).
select claim_group_id, gross_drug_cost, patient_pay_amt, lics_amt, cpp_amt, mfr_discount_amt
from {{ ref('fct_pde_claims') }}
where abs(gross_drug_cost - (patient_pay_amt + lics_amt + cpp_amt + mfr_discount_amt)) > 0.011
   or abs(gross_drug_cost - (gdcb + gdca)) > 0.011
