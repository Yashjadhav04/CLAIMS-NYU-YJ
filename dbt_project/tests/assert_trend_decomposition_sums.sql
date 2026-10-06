-- utilization + mix + price must equal the total PMPM change exactly; and the drug-level view must tie to the same total.
select measure, residual
from {{ ref('mart_trend_drivers') }}
where abs(residual) > 0.000001

union all

select d.measure, abs(d.drug_total - t.pmpm_change) as residual
from (
    select measure, sum(volume_effect + price_effect) as drug_total
    from {{ ref('mart_trend_by_drug') }}
    group by 1
) d
join {{ ref('mart_trend_drivers') }} t using (measure)
where abs(d.drug_total - t.pmpm_change) > 0.000001
