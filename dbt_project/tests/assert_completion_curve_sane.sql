-- The cumulative completion curve must be non-decreasing, start above zero, and end essentially at 1.
select a.dev_day, a.completion_factor, b.completion_factor as next_factor
from {{ ref('mart_completion_curve') }} a
join {{ ref('mart_completion_curve') }} b on b.dev_day = a.dev_day + 1
where b.completion_factor < a.completion_factor - 0.0000001

union all

select dev_day, completion_factor, null
from {{ ref('mart_completion_curve') }}
where completion_factor <= 0
   or completion_factor > 1.0000001
   or (dev_day = {{ var('completion_max_dev_days') }} and completion_factor < 0.995)
