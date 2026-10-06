{#- Top drugs by gross cost, current-year YTD (through var trend_end_month) with prior-year YTD comparison. -#}
with params as (
    select
        cast('{{ var("trend_end_month") }}' as date) as cur_end,
        date_trunc('year', cast('{{ var("trend_end_month") }}' as date))::date as cur_start,
        (date_trunc('year', cast('{{ var("trend_end_month") }}' as date)) - interval 1 year)::date as pri_start,
        (cast('{{ var("trend_end_month") }}' as date) - interval 1 year)::date as pri_end
),

mm as (
    select 'current' as period, count(*) as member_months
    from {{ ref('int_member_months') }} m, params p where m.month_start between p.cur_start and p.cur_end
    union all
    select 'prior', count(*)
    from {{ ref('int_member_months') }} m, params p where m.month_start between p.pri_start and p.pri_end
),

cur as (
    select
        f.drug_id,
        count(*) as claims,
        count(distinct f.member_id) as members,
        sum(f.gross_drug_cost) as gross_drug_cost,
        sum(f.net_plan_liability) as net_plan_liability
    from {{ ref('fct_pde_claims') }} f, params p
    where f.incurred_month between p.cur_start and p.cur_end
    group by 1
),

pri as (
    select f.drug_id, sum(f.gross_drug_cost) as gross_drug_cost
    from {{ ref('fct_pde_claims') }} f, params p
    where f.incurred_month between p.pri_start and p.pri_end
    group by 1
),

ranked as (
    select
        c.*,
        d.drug_label,
        d.generic_name,
        d.therapeutic_class,
        d.tier,
        d.drug_kind,
        c.gross_drug_cost / (select member_months from mm where period = 'current') as gross_pmpm,
        coalesce(p.gross_drug_cost, 0) / (select member_months from mm where period = 'prior') as gross_pmpm_prior,
        c.gross_drug_cost / sum(c.gross_drug_cost) over () as share_of_gross,
        row_number() over (order by c.gross_drug_cost desc) as cost_rank
    from cur c
    join {{ ref('stg_drugs') }} d using (drug_id)
    left join pri p using (drug_id)
)

select
    *,
    sum(share_of_gross) over (order by cost_rank) as cumulative_share_of_gross,
    case when gross_pmpm_prior > 0 then gross_pmpm / gross_pmpm_prior - 1 end as gross_pmpm_yoy
from ranked
order by cost_rank
