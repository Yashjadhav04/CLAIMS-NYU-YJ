{#-
  Drug-level contribution to the YoY PMPM change (same windows as mart_trend_drivers):
    pmpm_change = volume_effect + price_effect, where
    volume_effect = (u1 - u0) * p0   (new drugs: p0 := p1)
    price_effect  = u1 * (p1 - p0)
  Answers "which drugs moved the trend?" for the leadership view.
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
, drug_{{ m }} as (
    select
        '{{ m }}' as measure,
        coalesce(c.drug_id, p.drug_id) as drug_id,
        coalesce(p.days_supply, 0) / (select member_months from mm where period = 'prior') as u0,
        coalesce(c.days_supply, 0) / (select member_months from mm where period = 'current') as u1,
        case when coalesce(p.days_supply, 0) > 0 then p.{{ m }} / p.days_supply
             else c.{{ m }} / nullif(c.days_supply, 0) end as p0,
        coalesce(c.{{ m }} / nullif(c.days_supply, 0), 0) as p1,
        coalesce(p.{{ m }}, 0) / (select member_months from mm where period = 'prior') as pmpm_prior,
        coalesce(c.{{ m }}, 0) / (select member_months from mm where period = 'current') as pmpm_current
    from (select * from drug_period where period = 'current') c
    full outer join (select * from drug_period where period = 'prior') p on c.drug_id = p.drug_id
)
{% endfor %}

select
    x.measure,
    x.drug_id,
    d.drug_label,
    d.generic_name,
    d.therapeutic_class,
    d.tier,
    d.drug_kind,
    x.pmpm_prior,
    x.pmpm_current,
    x.pmpm_current - x.pmpm_prior as pmpm_change,
    (x.u1 - x.u0) * x.p0 as volume_effect,
    case when x.u1 > 0 then x.u1 * (x.p1 - x.p0) else 0 end as price_effect,
    x.u0 = 0 as is_new_in_current,
    row_number() over (partition by x.measure order by abs(x.pmpm_current - x.pmpm_prior) desc) as impact_rank
from (
    {% for m in measures %}
    select * from drug_{{ m }}
    {% if not loop.last %}union all{% endif %}
    {% endfor %}
) x
join {{ ref('stg_drugs') }} d using (drug_id)
