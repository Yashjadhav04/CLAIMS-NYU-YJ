-- Under the 2025+ design no member's annual TrOOP (patient pay + LICS) may exceed the out-of-pocket threshold.
-- $1.00 tolerance covers per-claim cent rounding across a year of claims.
select member_id, benefit_year, sum(troop_amt) as annual_troop, max(troop_threshold) as cap
from {{ ref('fct_pde_claims') }}
where benefit_design = 'ira'
group by 1, 2
having sum(troop_amt) > max(troop_threshold) + 1.00
