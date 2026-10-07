-- Real CMS data. Run: duckdb < sql/public/01_top_drugs_by_year.sql   (from the repo root, after `make public`)
-- Top 10 drugs by 2024 gross spend with 2020 comparison.
select Brnd_Name, Gnrc_Name,
       round(Tot_Spndng_2020/1e9, 2) as spend_2020_b, round(Tot_Spndng_2024/1e9, 2) as spend_2024_b,
       round(Tot_Spndng_2024/Tot_Spndng_2020 - 1, 3) as growth
from read_csv_auto('data/public/cms_partd_spending_by_drug_annual.csv')
where Mftr_Name = 'Overall'
order by Tot_Spndng_2024 desc nulls last
limit 10;
