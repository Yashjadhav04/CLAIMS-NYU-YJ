{#- How concentrated is annual gross drug cost? Top 1% / 5% / 10% of members' share of total (per benefit year). -#}
with member_year as (
    select benefit_year, member_id, sum(gross_drug_cost) as gross_drug_cost, sum(net_plan_liability) as net_plan_liability
    from {{ ref('fct_pde_claims') }}
    group by 1, 2
),

ranked as (
    select
        *,
        percent_rank() over (partition by benefit_year order by gross_drug_cost desc) as pct_rank,
        sum(gross_drug_cost) over (partition by benefit_year) as total_gross,
        sum(net_plan_liability) over (partition by benefit_year) as total_net,
        count(*) over (partition by benefit_year) as members_with_claims
    from member_year
),

buckets as (
    select 'Top 1%' as bucket, 0.01 as cutoff union all
    select 'Top 5%', 0.05 union all
    select 'Top 10%', 0.10
)

select
    r.benefit_year,
    b.bucket,
    b.cutoff,
    max(r.members_with_claims) as members_with_claims,
    count(*) as members_in_bucket,
    sum(r.gross_drug_cost) as gross_drug_cost,
    sum(r.gross_drug_cost) / max(r.total_gross) as share_of_gross,
    sum(r.net_plan_liability) / max(r.total_net) as share_of_net_plan_liability
from ranked r
join buckets b on r.pct_rank <= b.cutoff
group by 1, 2, 3
order by 1, 3
