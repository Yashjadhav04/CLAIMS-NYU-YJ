# Runbook: refreshing the analysis

Written the way a team would hand the process to a new analyst. Each step says what to run, what to look at, and when to stop.

## Quarterly refresh of the real-data views (about 15 minutes)
1. `make public` downloads the newest CMS files (annual spending, quarterly spending, monthly enrollment, prescriber-by-geography) and rebuilds `reports/partd_public_cms_dashboard.html`.
2. Open the **Data checks** tab. All rows must read `pass`. If one fails, stop: a file layout or definition probably changed. Do not publish.
3. Skim the **Overview** insights. Anything that looks surprising (a sign flip, a drug jumping rank) gets traced to its source row before it goes into a memo.
4. `make excel` rebuilds `reports/partd_analyst_pack.xlsx`. Open it in Excel or LibreOffice and recalculate; the Data_Checks sheet should match the dashboard.
5. `make briefing` regenerates `docs/BRIEFING.md`. Read it against the dashboard and edit the "What I would tell leadership" section by hand before sending.
6. `make test` must pass.

## When CMS publishes a new annual year
- The annual file gains a new year column. Add the year to `YEARS` in `public_cms.py` and `public_extra.py`; the tests will flag anything that no longer holds.
- Move 2025 out of "preliminary" only when it is in the annual file.

## Monthly refresh of the synthetic plan model
`make all` rebuilds data, dbt models (86 checks), forecast, dashboard, export and tests. In production the only change is step 1: load real PDE extracts instead of the generator, then run the same models.

## Escalation rules
- Any check outside tolerance: stop and report.
- Any figure that moves more than 10% from the last release without an explanation: trace it before it is shared.
- Anything that depends on rebates or plan-level detail: say it is not in the public data.

## What this replaces
Manual copy-and-paste from CMS downloads into spreadsheets, and one-off reconciliation of files by eye. The checks and the formulas in the workbook do that now.
