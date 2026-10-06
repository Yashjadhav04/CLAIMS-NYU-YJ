/* 02_pmpm.sas
   Monthly gross and net plan PMPM. Net plan liability = covered plan paid less estimated reinsurance.
   Reinsurance rate is illustrative (see dbt_project/seeds/benefit_params.csv). Member months from enrollment.
   NOT RUN: reference translation; verify before use. */

proc import datafile="data/raw/enrollment.csv" out=enroll dbms=csv replace; guessingrows=max; run;

data member_months;
  set enroll;
  /* one row per member-month: expand enrollment spans */
  format month date9.;
  month = intnx('month', start_date, 0, 'b');
  do while (month <= coalesce(end_date, '30SEP2026'd));
    output;
    month = intnx('month', month, 1, 'b');
  end;
  keep member_id month;
run;

proc sql;
  create table mm as
    select month, count(*) as member_months from member_months group by month;

  create table cost as
    select intnx('month', fill_date, 0, 'b') as month format=date9.,
           count(*) as claims,
           sum(gross_drug_cost) as gross,
           sum(cpp_amt) as cpp,
           sum(gdca) as gdca
    from final_action
    group by calculated month;

  create table pmpm as
    select m.month, m.member_months, c.claims,
           c.gross / m.member_months as gross_pmpm format=dollar10.2,
           (c.cpp - 0.2 * c.gdca) / m.member_months as net_plan_pmpm format=dollar10.2   /* 0.2 = illustrative reinsurance rate */
    from mm m left join cost c on m.month = c.month
    order by m.month;
quit;

proc sgplot data=pmpm;
  series x=month y=net_plan_pmpm;
  title "Net plan PMPM (synthetic)";
run;
