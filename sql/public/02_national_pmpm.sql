-- Gross PMPM by year: CMS spending / (sum of monthly Part D enrollees). Real data, both files from data.cms.gov.
with spend as (
  select 2020 as yr, sum(Tot_Spndng_2020) as s from read_csv_auto('data/public/cms_partd_spending_by_drug_annual.csv') where Mftr_Name='Overall' union all
  select 2021, sum(Tot_Spndng_2021) from read_csv_auto('data/public/cms_partd_spending_by_drug_annual.csv') where Mftr_Name='Overall' union all
  select 2022, sum(Tot_Spndng_2022) from read_csv_auto('data/public/cms_partd_spending_by_drug_annual.csv') where Mftr_Name='Overall' union all
  select 2023, sum(Tot_Spndng_2023) from read_csv_auto('data/public/cms_partd_spending_by_drug_annual.csv') where Mftr_Name='Overall' union all
  select 2024, sum(Tot_Spndng_2024) from read_csv_auto('data/public/cms_partd_spending_by_drug_annual.csv') where Mftr_Name='Overall'),
mm as (
  select YEAR as yr, sum(try_cast(PRSCRPTN_DRUG_TOT_BENES as double)) as member_months
  from read_csv_auto('data/public/cms_monthly_enrollment.csv', all_varchar=true)
  where BENE_GEO_LVL='National' and MONTH <> 'Year' and YEAR::int between 2020 and 2024 group by 1)
select spend.yr, round(s/1e9,1) as spend_b, round(member_months/1e6,1) as member_months_m, round(s/member_months,2) as gross_pmpm
from spend join mm on spend.yr = mm.yr::int order by 1;
