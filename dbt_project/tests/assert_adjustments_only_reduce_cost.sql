-- Final-action amounts for adjusted claims must come from the adjustment record, and in this data set adjustments are
-- price reductions: final gross must be below the original submission's gross.
select f.claim_group_id, f.gross_drug_cost as final_gross, o.gross_drug_cost as original_gross
from {{ ref('fct_pde_claims') }} f
join {{ ref('stg_pde_submissions') }} o
  on o.claim_group_id = f.claim_group_id
 and o.dcs_status = 'A'
 and o.adjustment_deletion_code = ''
where f.was_adjusted
  and f.gross_drug_cost >= o.gross_drug_cost
