select
    e.member_id,
    e.month_start,
    e.benefit_year,
    e.plan_id,
    p.contract_id,
    p.plan_type,
    e.lis_flag
from {{ ref('stg_enrollment') }} e
join {{ ref('stg_plans') }} p using (plan_id)
