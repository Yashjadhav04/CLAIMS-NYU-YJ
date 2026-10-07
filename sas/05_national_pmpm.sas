/* 05_national_pmpm.sas
   National gross PMPM from the two public CMS files, and the use-vs-price split.
   NOT RUN: reference translation of src/partd/public_extra.py (national_pmpm, pmpm_bridge). Verify before relying on it. */

proc import datafile="data/public/cms_partd_spending_by_drug_annual.csv" out=annual dbms=csv replace; guessingrows=max; run;
proc import datafile="data/public/cms_monthly_enrollment.csv" out=enroll dbms=csv replace; guessingrows=max; run;

data spend_y;
  set annual(where=(Mftr_Name='Overall'));
  array s{5} Tot_Spndng_2020-Tot_Spndng_2024;
  array c{5} Tot_Clms_2020-Tot_Clms_2024;
  do i=1 to 5; year=2019+i; spend=s{i}; claims=c{i}; output; end;
  keep year spend claims;
run;
proc means data=spend_y noprint nway; class year; var spend claims; output out=tot sum=; run;

proc sql;
  create table mm as
    select input(put(year,4.),4.) as year, sum(input(PRSCRPTN_DRUG_TOT_BENES, best32.)) as member_months
    from enroll
    where BENE_GEO_LVL='National' and MONTH ne 'Year' and year between 2020 and 2024
    group by year;
  create table pmpm as
    select t.year, t.spend, t.claims, m.member_months,
           t.spend/m.member_months as gross_pmpm format=dollar10.2,
           t.claims/m.member_months*1000 as claims_per_1000 format=comma10.1,
           t.spend/t.claims as spend_per_claim format=dollar10.2
    from tot t join mm m on t.year=m.year order by t.year;
quit;

/* log-share split of the year-over-year PMPM change into claims-per-member and cost-per-claim */
data bridge;
  set pmpm;
  lag_p = lag(gross_pmpm); lag_f = lag(claims_per_1000); lag_c = lag(spend_per_claim);
  if _n_ > 1 then do;
    chg = gross_pmpm - lag_p;
    lf = log(claims_per_1000/lag_f); lp = log(spend_per_claim/lag_c);
    use_effect = chg*lf/(lf+lp); cost_effect = chg*lp/(lf+lp);
  end;
run;
proc print data=bridge noobs; run;
