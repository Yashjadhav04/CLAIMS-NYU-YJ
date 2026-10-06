{#- Dollars and claims by incurred month and the benefit phase a claim STARTED in. Catastrophic dollars (GDCA) are exact. -#}
select
    incurred_month,
    benefit_year,
    benefit_phase_at_start,
    count(*) as claims,
    sum(gross_drug_cost) as gross_drug_cost,
    sum(gdca) as catastrophic_gross_drug_cost,
    sum(patient_pay_amt) as patient_pay,
    sum(lics_amt) as lics,
    sum(mfr_discount_amt) as mfr_discount,
    sum(cpp_amt) as covered_plan_paid,
    sum(reinsurance_est) as reinsurance_est,
    sum(net_plan_liability) as net_plan_liability
from {{ ref('fct_pde_claims') }}
group by 1, 2, 3
