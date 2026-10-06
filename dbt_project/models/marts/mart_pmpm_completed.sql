{#-
  mart_pmpm_monthly with additive measures grossed up by the completion factor for the incurred month, so recent
  months are comparable with mature ones. Member months are not adjusted. The factor is estimated on gross drug cost and
  applied uniformly to dollars and claim counts (an explicit simplification, documented in docs/ASSUMPTIONS.md).
  Months at least completion_max_dev_days past month end are treated as fully developed (factor = 1).
-#}
with base as (
    select
        p.*,
        datediff('day', last_day(p.incurred_month), cast('{{ var("as_of_date") }}' as date)) as dev_days_elapsed
    from {{ ref('mart_pmpm_monthly') }} p
),

factored as (
    select
        b.*,
        case
            when b.dev_days_elapsed >= {{ var('completion_max_dev_days') }} then 1.0
            else f.completion_factor
        end as completion_factor
    from base b
    left join {{ ref('mart_completion_curve') }} f on f.dev_day = b.dev_days_elapsed
    where b.dev_days_elapsed >= 0
)

select
    incurred_month,
    benefit_year,
    plan_type,
    lis_flag,
    member_months,
    dev_days_elapsed,
    completion_factor,
    claims as claims_reported,
    claims / completion_factor as claims,
    days_supply / completion_factor as days_supply,
    gross_drug_cost as gross_drug_cost_reported,
    gross_drug_cost / completion_factor as gross_drug_cost,
    patient_pay / completion_factor as patient_pay,
    lics / completion_factor as lics,
    mfr_discount / completion_factor as mfr_discount,
    covered_plan_paid / completion_factor as covered_plan_paid,
    reinsurance_est / completion_factor as reinsurance_est,
    net_plan_liability as net_plan_liability_reported,
    net_plan_liability / completion_factor as net_plan_liability
from factored
