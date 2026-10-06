-- Duplicate pharmacy submissions are cleaned up by deletion records. After final-action logic, the same member must not
-- have two fills of the same drug on the same day.
select member_id, drug_id, fill_date, count(*) as n
from {{ ref('fct_pde_claims') }}
group by 1, 2, 3
having count(*) > 1
