select
    incurred_month,
    therapeutic_class,
    count(*) as claims,
    count(distinct member_id) as members,
    sum(days_supply) as days_supply,
    sum(gross_drug_cost) as gross_drug_cost,
    sum(net_plan_liability) as net_plan_liability
from {{ ref('fct_pde_claims') }}
group by 1, 2
