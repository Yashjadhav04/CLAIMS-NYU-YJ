{#-
  PDE rejection (CMS edit) monitoring by month the rejection was received and edit code.
  reject_rate = rejected submissions / all PDE records received that month.
  Unresolved rejections are claims with no later accepted record: gross drug cost that is not in payment reconciliation.
-#}
with submissions as (
    select date_trunc('month', received_date)::date as received_month, count(*) as submissions_in_month
    from {{ ref('stg_pde_submissions') }}
    group by 1
),

rejects as (
    select
        date_trunc('month', first_reject_date)::date as received_month,
        first_edit_code as edit_code,
        count(*) as rejects,
        sum(case when is_resolved then 1 else 0 end) as resolved,
        sum(case when not is_resolved then 1 else 0 end) as unresolved,
        sum(case when not is_resolved then gross_drug_cost else 0 end) as gross_at_risk_unresolved,
        sum(gross_drug_cost) as gross_rejected,
        avg(days_to_resolve) as avg_days_to_resolve,
        median(days_to_resolve) as median_days_to_resolve
    from {{ ref('int_pde_rejects') }}
    group by 1, 2
)

select
    r.received_month,
    r.edit_code,
    s.submissions_in_month,
    r.rejects,
    r.resolved,
    r.unresolved,
    r.gross_rejected,
    r.gross_at_risk_unresolved,
    r.avg_days_to_resolve,
    r.median_days_to_resolve,
    r.rejects::double / s.submissions_in_month as reject_rate
from rejects r
join submissions s using (received_month)
order by 1, 2
