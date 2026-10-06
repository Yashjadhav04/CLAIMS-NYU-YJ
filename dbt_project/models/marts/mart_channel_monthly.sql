select
    incurred_month,
    pharmacy_type,
    count(*) as claims,
    sum(days_supply) as days_supply,
    sum(gross_drug_cost) as gross_drug_cost,
    sum(net_plan_liability) as net_plan_liability,
    sum(dispensing_fee) as dispensing_fees
from {{ ref('fct_pde_claims') }}
group by 1, 2
