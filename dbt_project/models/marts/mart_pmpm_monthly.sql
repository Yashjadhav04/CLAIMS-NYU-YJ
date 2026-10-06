{#-
  Core actuarial measures by incurred month x plan type x LIS status, AS REPORTED (not completed for late-arriving
  claims; see mart_pmpm_completed). Member months come from enrollment, not claims, so months with no utilization
  still appear.
-#}
with member_months as (
    select month_start as incurred_month, plan_type, lis_flag, count(*) as member_months
    from {{ ref('int_member_months') }}
    group by 1, 2, 3
),

claims as (
    select
        incurred_month,
        plan_type,
        lis_flag,
        count(*) as claims,
        sum(days_supply) as days_supply,
        sum(gross_drug_cost) as gross_drug_cost,
        sum(patient_pay_amt) as patient_pay,
        sum(lics_amt) as lics,
        sum(mfr_discount_amt) as mfr_discount,
        sum(cpp_amt) as covered_plan_paid,
        sum(reinsurance_est) as reinsurance_est,
        sum(net_plan_liability) as net_plan_liability,
        sum(case when is_generic then 1 else 0 end) as generic_claims,
        sum(case when is_specialty then 1 else 0 end) as specialty_claims,
        sum(case when is_specialty then gross_drug_cost else 0 end) as specialty_gross,
        sum(case when days_supply_bucket = '90-day' then 1 else 0 end) as claims_90day,
        sum(case when pharmacy_type = 'Mail order' then 1 else 0 end) as mail_claims
    from {{ ref('fct_pde_claims') }}
    group by 1, 2, 3
)

select
    mm.incurred_month,
    extract(year from mm.incurred_month)::integer as benefit_year,
    mm.plan_type,
    mm.lis_flag,
    mm.member_months,
    coalesce(c.claims, 0) as claims,
    coalesce(c.days_supply, 0) as days_supply,
    coalesce(c.gross_drug_cost, 0) as gross_drug_cost,
    coalesce(c.patient_pay, 0) as patient_pay,
    coalesce(c.lics, 0) as lics,
    coalesce(c.mfr_discount, 0) as mfr_discount,
    coalesce(c.covered_plan_paid, 0) as covered_plan_paid,
    coalesce(c.reinsurance_est, 0) as reinsurance_est,
    coalesce(c.net_plan_liability, 0) as net_plan_liability,
    coalesce(c.generic_claims, 0) as generic_claims,
    coalesce(c.specialty_claims, 0) as specialty_claims,
    coalesce(c.specialty_gross, 0) as specialty_gross,
    coalesce(c.claims_90day, 0) as claims_90day,
    coalesce(c.mail_claims, 0) as mail_claims,
    {{ pmpm('coalesce(c.gross_drug_cost, 0)', 'mm.member_months') }} as gross_pmpm,
    {{ pmpm('coalesce(c.net_plan_liability, 0)', 'mm.member_months') }} as net_plan_pmpm,
    {{ pmpm('coalesce(c.claims, 0) * 1000.0', 'mm.member_months') }} as claims_per_1000_mm,
    {{ safe_div('coalesce(c.generic_claims, 0)', 'c.claims') }} as generic_dispensing_rate,
    {{ safe_div('coalesce(c.gross_drug_cost, 0)', 'c.claims') }} as gross_cost_per_claim
from member_months mm
left join claims c using (incurred_month, plan_type, lis_flag)
