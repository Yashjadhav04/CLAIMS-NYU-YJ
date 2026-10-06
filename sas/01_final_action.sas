/* 01_final_action.sas
   PDE final-action logic: latest accepted record per claim; drop deletions.
   REFERENCE TRANSLATION of dbt_project/models/intermediate/int_pde_final_action.sql.
   NOT RUN: no SAS licence was available when this repo was built. Check on your own SAS before relying on it. */

%let in_lib = work;            /* point at the library holding pde_submissions (CSV import or libname) */

proc import datafile="data/raw/pde_submissions.csv" out=&in_lib..pde_submissions dbms=csv replace;
  guessingrows=max;
run;

/* accepted records only; rejected submissions (DCS status R) never count */
proc sort data=&in_lib..pde_submissions(where=(dcs_status='A')) out=accepted;
  by claim_group_id descending received_date descending pde_id;
run;

/* the first row per claim after this sort is the final-action record */
data final_action;
  set accepted;
  by claim_group_id;
  if first.claim_group_id;
  if adjustment_deletion_code = 'D' then delete;
  gross_drug_cost = gdcb + gdca;
run;

proc sql;
  title "Final-action check";
  select count(*) as claims, sum(gross_drug_cost) as gross format=dollar16.2 from final_action;
quit;
