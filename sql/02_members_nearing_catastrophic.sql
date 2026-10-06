-- Members within $250 of the TrOOP threshold in the latest month: next-quarter plan liability risk.
select member_id, benefit_year, max(cum_troop_before + troop_amt) as troop_to_date, max(troop_threshold) as threshold
from fct_pde_claims
where benefit_year = (select max(benefit_year) from fct_pde_claims)
group by 1, 2
having max(cum_troop_before + troop_amt) between max(troop_threshold) - 250 and max(troop_threshold) - 0.01
order by threshold - troop_to_date
limit 100;
