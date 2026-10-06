-- Claims that were rejected and never resolved, and claims whose latest accepted record is a deletion, must not be in the fact table.
with unresolved as (
    select claim_group_id from {{ ref('int_pde_rejects') }} where not is_resolved
),

deleted as (
    select claim_group_id
    from (
        select
            claim_group_id,
            adjustment_deletion_code,
            row_number() over (partition by claim_group_id order by received_date desc, pde_id desc) as rn
        from {{ ref('stg_pde_submissions') }}
        where dcs_status = 'A'
    )
    where rn = 1 and adjustment_deletion_code = 'D'
)

select f.claim_group_id
from {{ ref('fct_pde_claims') }} f
where f.claim_group_id in (select claim_group_id from unresolved)
   or f.claim_group_id in (select claim_group_id from deleted)
