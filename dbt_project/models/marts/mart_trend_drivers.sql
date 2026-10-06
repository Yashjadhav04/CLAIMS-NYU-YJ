{#-
  Year-over-year PMPM trend decomposition: current-year YTD vs prior-year YTD (through var trend_end_month).

  Drug-level price / volume / mix decomposition. For drug i: u = days supply per member month, p = cost per day supply.
    utilization  = (U1/U0 - 1) * PMPM0                      overall days-supply growth at prior mix and price
    mix (exist.) = sum[(u1 - u0*U1/U0) * p0]                shift of days supply between drugs that existed in both
    mix (new)    = sum[u1 * p1]  over drugs new in current  new drugs enter at their own price (p0 := p1)
    price        = sum[u1 * (p1 - p0)]                      unit-cost change on current volume
  and utilization + mix + price = PMPM1 - PMPM0 exactly. A test enforces that identity.

  Run for two measures: gross drug cost, and net plan liability. For net plan liability, "price" also absorbs
  benefit-design / cost-share effects (it is net cost per day supply), which is called out in the docs.
-#}
{% set measures = ['gross_drug_cost', 'net_plan_liability'] %}

with params as (
    select
        cast('{{ var("trend_end_month") }}' as date) as cur_end,
        date_trunc('year', cast('{{ var("trend_end_month") }}' as date))::date as cur_start,
        (date_trunc('year', cast('{{ var("trend_end_month") }}' as date)) - interval 1 year)::date as pri_start,
        (cast('{{ var("trend_end_month") }}' as date) - interval 1 year)::date as pri_end
),

mm as (
    select 'current' as period, count(*) as member_months
    from {{ ref('int_member_months') }} m, params p
    where m.month_start between p.cur_start and p.cur_end
    union all
    select 'prior', count(*)
    from {{ ref('int_member_months') }} m, params p
    where m.month_start between p.pri_start and p.pri_end
),

drug_period as (
    select
        'current' as period, f.drug_id,
        sum(f.days_supply) as days_supply,
        sum(f.gross_drug_cost) as gross_drug_cost,
        sum(f.net_plan_liability) as net_plan_liability
    from {{ ref('fct_pde_claims') }} f, params p
    where f.incurred_month between p.cur_start and p.cur_end
    group by 1, 2
    union all
    select
        'prior', f.drug_id,
        sum(f.days_supply), sum(f.gross_drug_cost), sum(f.net_plan_liability)
    from {{ ref('fct_pde_claims') }} f, params p
    where f.incurred_month between p.pri_start and p.pri_end
    group by 1, 2
)

{% for m in measures %}
, base_{{ m }} as (
    select
        coalesce(c.drug_id, p.drug_id) as drug_id,
        coalesce(p.days_supply, 0) / (select member_months from mm where period = 'prior') as u0,
        coalesce(c.days_supply, 0) / (select member_months from mm where period = 'current') as u1,
        case when coalesce(p.days_supply, 0) > 0 then p.{{ m }} / p.days_supply
             else c.{{ m }} / nullif(c.days_supply, 0) end as p0,
        coalesce(c.{{ m }} / nullif(c.days_supply, 0), 0) as p1
    from (select * from drug_period where period = 'current') c
    full outer join (select * from drug_period where period = 'prior') p on c.drug_id = p.drug_id
),

totals_{{ m }} as (
    select
        sum(u0) as u0_total,
        sum(u1) as u1_total,
        sum(u0 * p0) as pmpm0,
        sum(u1 * p1) as pmpm1
    from base_{{ m }}
),

effects_{{ m }} as (
    select
        '{{ m }}' as measure,
        t.pmpm0 as pmpm_prior,
        t.pmpm1 as pmpm_current,
        t.pmpm1 - t.pmpm0 as pmpm_change,
        (t.u1_total / t.u0_total - 1) * t.pmpm0 as utilization_effect,
        sum(case when b.u0 > 0 then (b.u1 - b.u0 * t.u1_total / t.u0_total) * b.p0 else 0 end) as mix_effect_existing,
        sum(case when b.u0 = 0 then b.u1 * b.p0 else 0 end) as mix_effect_new_drugs,
        sum(case when b.u1 > 0 then b.u1 * (b.p1 - b.p0) else 0 end) as price_effect
    from base_{{ m }} b
    cross join totals_{{ m }} t
    group by t.u0_total, t.u1_total, t.pmpm0, t.pmpm1
)
{% endfor %}

select
    *,
    pmpm_change - (utilization_effect + mix_effect_existing + mix_effect_new_drugs + price_effect) as residual,
    pmpm_change / pmpm_prior as pmpm_change_pct,
    (select cur_end from params) as period_end,
    (select cur_start from params) as current_start,
    (select pri_start from params) as prior_start
from (
    {% for m in measures %}
    select * from effects_{{ m }}
    {% if not loop.last %}union all{% endif %}
    {% endfor %}
)
