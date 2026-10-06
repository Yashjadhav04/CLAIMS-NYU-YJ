{#-
  Claim-level fact table: one row per final-action pharmacy claim.

  Benefit phase is RE-DERIVED here from cumulative gross drug cost and cumulative TrOOP (true out-of-pocket) using
  the benefit parameters in seeds/benefit_params.csv. It is not read off the source data, which lets the singular
  tests cross-check the derived phase against the dollars that were actually paid in each claim.

  Net plan liability = covered plan paid (CPP) - estimated CMS reinsurance on catastrophic gross drug cost (GDCA).
-#}
with claims as (
    select
        f.claim_group_id,
        f.member_id,
        f.drug_id,
        f.pharmacy_id,
        f.fill_date,
        date_trunc('month', f.fill_date)::date as incurred_month,
        extract(year from f.fill_date)::integer as benefit_year,
        f.days_supply,
        f.quantity_dispensed,
        f.ingredient_cost,
        f.dispensing_fee,
        f.gdcb,
        f.gdca,
        f.gross_drug_cost,
        f.patient_pay_amt,
        f.lics_amt,
        f.cpp_amt,
        f.mfr_discount_amt,
        f.was_adjusted,
        f.first_accepted_received_date,
        datediff('day', f.fill_date, f.first_accepted_received_date) as submission_lag_days,
        d.generic_name,
        d.brand_name,
        d.drug_label,
        d.therapeutic_class,
        d.tier,
        d.drug_kind,
        d.is_generic,
        d.is_specialty,
        d.is_applicable_drug,
        ph.pharmacy_type
    from {{ ref('int_pde_final_action') }} f
    join {{ ref('stg_drugs') }} d using (drug_id)
    join {{ ref('stg_pharmacies') }} ph using (pharmacy_id)
),

with_params as (
    select
        c.*,
        b.design as benefit_design,
        b.deductible,
        b.icl_limit,
        b.troop_threshold,
        b.reins_applicable,
        b.reins_nonapplicable,
        -- TrOOP: member + LIS payments; under the legacy design the manufacturer gap discount also counts
        c.patient_pay_amt + c.lics_amt
            + case when b.design = 'legacy' then c.mfr_discount_amt else 0 end as troop_amt
    from claims c
    join {{ ref('benefit_params') }} b on b.benefit_year = c.benefit_year
),

accumulated as (
    select
        *,
        coalesce(sum(gross_drug_cost) over w, 0) as cum_gross_before,
        coalesce(sum(troop_amt) over w, 0) as cum_troop_before
    from with_params
    window w as (
        partition by member_id, benefit_year
        order by fill_date, claim_group_id
        rows between unbounded preceding and 1 preceding
    )
)

select
    a.claim_group_id,
    a.member_id,
    a.drug_id,
    a.pharmacy_id,
    a.fill_date,
    a.incurred_month,
    a.benefit_year,
    a.days_supply,
    case when a.days_supply >= 84 then '90-day' else '30-day' end as days_supply_bucket,
    a.quantity_dispensed,
    a.ingredient_cost,
    a.dispensing_fee,
    a.gdcb,
    a.gdca,
    a.gross_drug_cost,
    a.patient_pay_amt,
    a.lics_amt,
    a.cpp_amt,
    a.mfr_discount_amt,
    a.gdca * case when a.is_applicable_drug then a.reins_applicable else a.reins_nonapplicable end as reinsurance_est,
    a.cpp_amt
        - a.gdca * case when a.is_applicable_drug then a.reins_applicable else a.reins_nonapplicable end
        as net_plan_liability,
    a.troop_amt,
    a.cum_gross_before,
    a.cum_troop_before,
    -- $0.25 tolerance on the TrOOP threshold: each claim amount is rounded to the cent, so a running sum of reported
    -- amounts drifts slightly from the exact running total that adjudication used.
    case
        when a.cum_troop_before >= a.troop_threshold - 0.25 then 'CATASTROPHIC'
        when a.cum_gross_before < a.deductible - 0.005 then 'DEDUCTIBLE'
        when a.benefit_design = 'legacy' and a.cum_gross_before >= a.icl_limit - 0.005 then 'COVERAGE_GAP'
        else 'INITIAL_COVERAGE'
    end as benefit_phase_at_start,
    a.gdca > 0 as reaches_catastrophic,
    a.benefit_design,
    a.deductible,
    a.troop_threshold,
    a.was_adjusted,
    a.first_accepted_received_date,
    a.submission_lag_days,
    a.generic_name,
    a.brand_name,
    a.drug_label,
    a.therapeutic_class,
    a.tier,
    a.drug_kind,
    a.is_generic,
    a.is_specialty,
    a.is_applicable_drug,
    a.pharmacy_type,
    m.plan_id,
    m.contract_id,
    m.plan_type,
    m.lis_flag
from accumulated a
left join {{ ref('int_member_months') }} m
    on m.member_id = a.member_id
   and m.month_start = a.incurred_month
