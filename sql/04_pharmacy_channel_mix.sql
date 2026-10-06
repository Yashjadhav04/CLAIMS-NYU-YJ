-- Retail vs mail vs specialty: share of gross cost and cost per claim, latest completed year to date.
select * from mart_channel_monthly
where incurred_month >= date_trunc('year', (select max(incurred_month) from mart_channel_monthly))
order by incurred_month;
