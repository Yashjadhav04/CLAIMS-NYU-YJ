# Runbook: refreshing the analysis

This runbook documents the refresh process. Each step states what to run, what to review, and when to escalate.

## Quarterly refresh of the real-data views (about 15 minutes)
1. `make public` downloads the newest CMS files (annual spending, quarterly spending, monthly enrollment, prescriber-by-geography) and rebuilds `reports/partd_public_cms_dashboard.html`.
2. Open the **Data checks** tab. All rows must read `pass`. If one fails, stop: a file layout or definition has likely changed. Do not release the results until resolved.
3. Review the **Overview** insights. Any unexpected movement (a sign change, a large change in drug rank) should be traced to its source row before inclusion in a memo.
4. `make excel` rebuilds `reports/partd_analyst_pack.xlsx`. Open it in Excel or LibreOffice and recalculate; the Data_Checks sheet should match the dashboard.
5. `make briefing` regenerates `docs/BRIEFING.md`. Read it against the dashboard and review and edit the "Key findings" section before distribution.
6. `make test` must pass.

## When CMS publishes a new annual year
- The annual file gains a new year column. Add the year to `YEARS` in `public_cms.py` and `public_extra.py`; the tests will flag anything that no longer holds.
- Move 2025 out of "preliminary" only when it is in the annual file.

## Monthly refresh of the synthetic plan model
`make all` rebuilds data, dbt models (86 checks), forecast, dashboard, export and tests. In production, the only change is step 1: load actual PDE extracts in place of the generator, then run the same models.

## Escalation rules
- Any check outside tolerance: pause and escalate.
- Any figure that moves more than 10% from the prior release without explanation: trace it before sharing.
- Anything that depends on rebates or plan-level detail: note that it is not available in the public data.

## Purpose of the automation
Replaces manual copying of CMS downloads into spreadsheets and ad hoc file reconciliation. The automated checks and workbook formulas now perform these steps.
