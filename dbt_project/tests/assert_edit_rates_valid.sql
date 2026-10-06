-- Reject rates must be proper fractions, and resolved + unresolved must add up to total rejects.
select received_month, edit_code, rejects, resolved, unresolved, reject_rate
from {{ ref('mart_pde_edit_monthly') }}
where reject_rate < 0 or reject_rate > 1
   or resolved + unresolved <> rejects
