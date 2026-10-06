-- Every month 2025+ that has actuals must have a budget row (the variance mart uses an inner join and would drop gaps silently).
select distinct p.incurred_month
from {{ ref('mart_pmpm_completed') }} p
left join {{ ref('budget_net_plan_pmpm') }} b on b.month_start = p.incurred_month
where p.benefit_year >= 2025
  and b.month_start is null
