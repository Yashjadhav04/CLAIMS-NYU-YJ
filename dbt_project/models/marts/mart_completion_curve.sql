{#-
  Claim completion (incurred-but-not-received) curve.

  For every "mature" incurred month (old enough that essentially all claims have arrived), compute the cumulative share
  of gross drug cost that had been received d days after month end, then average across mature months. That curve F(d)
  is the completion factor applied to recent months: completed = reported / F(days since month end).
  Beyond completion_max_dev_days the month is treated as fully developed (factor = 1).
-#}
{% set max_dev = var('completion_max_dev_days') %}

with claims as (
    select
        incurred_month,
        last_day(incurred_month) as month_end,
        gross_drug_cost,
        first_accepted_received_date as received_date
    from {{ ref('fct_pde_claims') }}
),

mature as (
    select distinct incurred_month, month_end
    from claims
    where month_end + {{ max_dev }} <= cast('{{ var("as_of_date") }}' as date)
),

totals as (
    select c.incurred_month, sum(c.gross_drug_cost) as total_gross
    from claims c
    join mature m using (incurred_month)
    group by 1
),

received_by_day as (
    select
        c.incurred_month,
        greatest(0, datediff('day', c.month_end, c.received_date)) as dev_day,
        sum(c.gross_drug_cost) as gross_received
    from claims c
    join mature m using (incurred_month)
    group by 1, 2
),

spine as (
    select m.incurred_month, d.dev_day
    from mature m
    cross join (select unnest(range(0, {{ max_dev }} + 1)) as dev_day) d
),

cumulative as (
    select
        s.incurred_month,
        s.dev_day,
        sum(coalesce(r.gross_received, 0)) over (
            partition by s.incurred_month order by s.dev_day
        ) / t.total_gross as cum_share
    from spine s
    left join received_by_day r using (incurred_month, dev_day)
    join totals t using (incurred_month)
)

select
    dev_day,
    avg(cum_share) as completion_factor,
    min(cum_share) as completion_factor_min,
    max(cum_share) as completion_factor_max,
    count(*) as mature_months_used
from cumulative
group by dev_day
order by dev_day
