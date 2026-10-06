-- The PMPM mart must not lose or invent dollars relative to the claim-level fact table.
with fact as (
    select sum(gross_drug_cost) as g, sum(net_plan_liability) as n, count(*) as c from {{ ref('fct_pde_claims') }}
),
mart as (
    select sum(gross_drug_cost) as g, sum(net_plan_liability) as n, sum(claims) as c from {{ ref('mart_pmpm_monthly') }}
)
select fact.g as fact_gross, mart.g as mart_gross, fact.c as fact_claims, mart.c as mart_claims
from fact, mart
where abs(fact.g - mart.g) > 0.05 or abs(fact.n - mart.n) > 0.05 or fact.c <> mart.c
