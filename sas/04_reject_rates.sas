/* 04_reject_rates.sas
   PDE reject rate by received month and edit code, plus unresolved rejects.
   NOT RUN: reference translation of mart_pde_edit_monthly; verify before use. */

proc sql;
  create table edits as
    select intnx('month', received_date, 0, 'b') as received_month format=date9.,
           edit_code,
           count(*) as submissions,
           sum(dcs_status = 'R') as rejects,
           calculated rejects / calculated submissions as reject_rate format=percent8.2
    from pde_submissions
    group by calculated received_month, edit_code
    order by received_month, edit_code;

  /* unresolved: claim has rejected submissions but no accepted record */
  create table unresolved as
    select r.claim_group_id, max(r.gdcb + r.gdca) as gross format=dollar12.2
    from pde_submissions r
    where r.dcs_status = 'R'
      and r.claim_group_id not in (select claim_group_id from pde_submissions where dcs_status = 'A')
    group by r.claim_group_id;
quit;

proc sgplot data=edits;
  vbar received_month / response=reject_rate;
  title "PDE reject rate (synthetic)";
run;
