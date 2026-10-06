/* 03_pvm_trend.sas
   Year-over-year PMPM trend: utilization, mix (existing drugs), mix (new drugs), price.
   Same algebra as dbt_project/models/marts/mart_trend_drivers.sql (tested there; the identity
   utilization + mix + price = PMPM1 - PMPM0 is enforced by a dbt test).
     u = days supply per member month, p = gross cost per day supply, U = sum of u, PMPM = sum of u*p
     utilization  = (U1/U0 - 1) * PMPM0
     mix existing = sum[(u1 - u0*U1/U0) * p0]          drugs present in both periods
     mix new      = sum[u1 * p1]                        drugs absent in the prior period
     price        = sum[u1 * (p1 - p0)]                 existing drugs
   Drugs that disappear contribute through u0 only (their p0 is used, u1 = 0).
   NOT RUN: reference translation; compare with the dbt output before using. */

%macro pvm(cur_start, cur_end, pri_start, pri_end, mm_cur, mm_pri);
  proc sql;
    create table cur as select drug_id, sum(days_supply) as ds, sum(gross_drug_cost) as cost
      from final_action where fill_date between &cur_start and &cur_end group by drug_id;
    create table pri as select drug_id, sum(days_supply) as ds, sum(gross_drug_cost) as cost
      from final_action where fill_date between &pri_start and &pri_end group by drug_id;
  quit;

  data drugs;
    merge cur(rename=(ds=ds1 cost=c1)) pri(rename=(ds=ds0 cost=c0));
    by drug_id;
    ds1 = coalesce(ds1,0); ds0 = coalesce(ds0,0); c1 = coalesce(c1,0); c0 = coalesce(c0,0);
    u1 = ds1/&mm_cur;  u0 = ds0/&mm_pri;
    p1 = ifn(ds1>0, c1/ds1, 0);
    p0 = ifn(ds0>0, c0/ds0, p1);       /* new drugs enter at their own price */
    is_new = (ds0 = 0 and ds1 > 0);
  run;

  proc sql noprint;
    select sum(u0), sum(u1), sum(u0*p0*(ds0>0)) into :U0 trimmed, :U1 trimmed, :PMPM0 trimmed from drugs;
  quit;

  data effects;
    set drugs end=last;
    retain mix_exist 0 mix_new 0 price 0;
    if is_new then mix_new + u1*p1;
    else do;
      mix_exist + (u1 - u0*&U1/&U0) * p0;
      price     + u1*(p1 - p0);
    end;
    if last then do;
      utilization = (&U1/&U0 - 1) * &PMPM0;
      total = utilization + mix_exist + mix_new + price;
      output;
    end;
    keep utilization mix_exist mix_new price total;
  run;

  proc print data=effects noobs; format _numeric_ dollar12.2; title "PMPM change decomposition"; run;
%mend;

/* example: %pvm('01JAN2026'd, '31JUL2026'd, '01JAN2025'd, '31JUL2025'd, 80000, 62000); */
