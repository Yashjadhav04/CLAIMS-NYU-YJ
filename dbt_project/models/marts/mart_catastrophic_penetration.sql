{#-
  Share of enrolled members who have entered the catastrophic phase, cumulative within the benefit year.
  Under the 2025+ design this is the "hit the out-of-pocket cap" rate, a key driver of mid/late-year plan liability.
-#}
with first_cat as (
    select member_id, benefit_year, min(incurred_month) as first_cat_month
    from {{ ref('fct_pde_claims') }}
    where reaches_catastrophic
    group by 1, 2
),

members_by_month as (
    select month_start as incurred_month, benefit_year, count(distinct member_id) as members_enrolled
    from {{ ref('int_member_months') }}
    group by 1, 2
)

select
    m.incurred_month,
    m.benefit_year,
    m.members_enrolled,
    count(distinct case when f.first_cat_month <= m.incurred_month then f.member_id end) as members_in_catastrophic_cum,
    count(distinct case when f.first_cat_month = m.incurred_month then f.member_id end) as members_entering_catastrophic,
    {{ safe_div(
        "count(distinct case when f.first_cat_month <= m.incurred_month then f.member_id end)::double",
        "m.members_enrolled") }} as pct_enrolled_in_catastrophic
from members_by_month m
left join first_cat f on f.benefit_year = m.benefit_year
group by m.incurred_month, m.benefit_year, m.members_enrolled
order by 1
