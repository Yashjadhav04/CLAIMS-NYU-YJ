{#-
  Actual (completed) vs synthetic budget net plan liability PMPM, by month, with year-to-date variance in dollars.
  Budget is the synthetic bid assumption in seeds/budget_net_plan_pmpm.csv (not real bid data).
-#}
with monthly as (
    select
        incurred_month,
        benefit_year,
        sum(member_months) as member_months,
        sum(net_plan_liability) as net_plan_liability,
        sum(gross_drug_cost) as gross_drug_cost,
        min(completion_factor) as completion_factor
    from {{ ref('mart_pmpm_completed') }}
    group by 1, 2
),

joined as (
    select
        m.*,
        b.budget_net_plan_pmpm,
        {{ pmpm('m.net_plan_liability', 'm.member_months') }} as actual_net_plan_pmpm,
        {{ pmpm('m.gross_drug_cost', 'm.member_months') }} as actual_gross_pmpm
    from monthly m
    join {{ ref('budget_net_plan_pmpm') }} b on b.month_start = m.incurred_month
)

select
    *,
    actual_net_plan_pmpm - budget_net_plan_pmpm as variance_pmpm,
    (actual_net_plan_pmpm - budget_net_plan_pmpm) / budget_net_plan_pmpm as variance_pct,
    (actual_net_plan_pmpm - budget_net_plan_pmpm) * member_months as variance_dollars,
    sum((actual_net_plan_pmpm - budget_net_plan_pmpm) * member_months) over (
        partition by benefit_year order by incurred_month
    ) as ytd_variance_dollars,
    sum(budget_net_plan_pmpm * member_months) over (
        partition by benefit_year order by incurred_month
    ) as ytd_budget_dollars
from joined
order by incurred_month
