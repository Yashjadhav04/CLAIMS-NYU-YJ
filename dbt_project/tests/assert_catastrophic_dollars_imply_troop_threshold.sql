-- Any claim with catastrophic gross drug cost (GDCA > 0) must have taken the member's cumulative TrOOP up to the threshold.
select claim_group_id, member_id, cum_troop_before, troop_amt, troop_threshold
from {{ claims_with_complete_history() }}
where gdca > 0
  and cum_troop_before + troop_amt < troop_threshold - 0.25  -- cent-rounding drift tolerance
