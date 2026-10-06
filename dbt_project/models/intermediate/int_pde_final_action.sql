{#-
  PDE "final action" logic.
  A pharmacy claim can appear many times in the PDE stream: the original record, later adjustments ('A'), and
  deletions ('D'). Rejected submissions (dcs_status = 'R') never count. The final-action record is the most recently
  received accepted record for each claim; if that record is a deletion the claim is dropped.
-#}
with accepted as (
    select
        *,
        min(received_date) over (partition by claim_group_id) as first_accepted_received_date,
        count(*) over (partition by claim_group_id) as accepted_record_count,
        row_number() over (
            partition by claim_group_id
            order by received_date desc, pde_id desc
        ) as recency_rank
    from {{ ref('stg_pde_submissions') }}
    where dcs_status = 'A'
)

select
    * exclude (recency_rank),
    adjustment_deletion_code = 'A' as was_adjusted
from accepted
where recency_rank = 1
  and adjustment_deletion_code <> 'D'
