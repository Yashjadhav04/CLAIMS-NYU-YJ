-- The 2024 insulin list-price cuts, visible in spend per dose unit.
select Brnd_Name, round(Avg_Spnd_Per_Dsg_Unt_Wghtd_2023,2) as unit_2023, round(Avg_Spnd_Per_Dsg_Unt_Wghtd_2024,2) as unit_2024,
       round(Chg_Avg_Spnd_Per_Dsg_Unt_23_24,3) as change, round(Tot_Spndng_2023/1e6,0) as spend_2023_m, round(Tot_Spndng_2024/1e6,0) as spend_2024_m
from read_csv_auto('data/public/cms_partd_spending_by_drug_annual.csv')
where Mftr_Name='Overall' and lower(Gnrc_Name) like '%insulin%' and Tot_Spndng_2023 > 5e8
order by Tot_Spndng_2023 desc;
