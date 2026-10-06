select
    member_id,
    cast(month_start as date) as month_start,
    extract(year from month_start)::integer as benefit_year,
    plan_id,
    lis_flag
from {{ source('raw', 'enrollment_monthly') }}
