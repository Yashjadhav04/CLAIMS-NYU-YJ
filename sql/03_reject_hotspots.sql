-- Edit codes and months with the highest unresolved dollars.
select received_month, edit_code, rejects, unresolved, gross_at_risk_unresolved, reject_rate
from mart_pde_edit_monthly
where unresolved > 0
order by gross_at_risk_unresolved desc
limit 20;
