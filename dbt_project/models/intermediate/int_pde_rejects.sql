{#-
  One row per claim that was rejected at least once by CMS edits, with its resolution status.
  A rejection that has no later accepted record is unresolved: that PDE is not in the payment reconciliation, so the
  associated gross drug cost is revenue at risk.
-#}
with rejects as (
    select
        claim_group_id,
        min(received_date) as first_reject_date,
        arg_min(edit_code, received_date) as first_edit_code,
        max(gross_drug_cost) as gross_drug_cost,
        max(cpp_amt) as covered_plan_paid,
        count(*) as reject_count
    from {{ ref('stg_pde_submissions') }}
    where dcs_status = 'R'
    group by claim_group_id
),

accepted as (
    select claim_group_id, min(received_date) as first_accepted_date
    from {{ ref('stg_pde_submissions') }}
    where dcs_status = 'A'
    group by claim_group_id
)

select
    r.*,
    a.first_accepted_date,
    a.first_accepted_date is not null as is_resolved,
    datediff('day', r.first_reject_date, a.first_accepted_date) as days_to_resolve
from rejects r
left join accepted a using (claim_group_id)
