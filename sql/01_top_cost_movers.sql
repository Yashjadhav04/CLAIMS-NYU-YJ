-- Which drugs added the most gross cost PMPM year over year?
select drug_label, therapeutic_class, pmpm_prior, pmpm_current, pmpm_change, volume_effect, price_effect
from mart_trend_by_drug where measure = 'gross_drug_cost'
order by impact_rank
limit 15;
