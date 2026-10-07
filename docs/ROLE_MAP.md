# Job description to repo evidence

| Requirement | Where it shows up |
|---|---|
| Write queries against pharmacy claims data | `dbt_project/models`, `sql/` (4 ad-hoc queries), PDE final-action logic |
| SAS and SQL | `sql/` (run and tested); `sas/` (reference translations, not run) |
| Excel | CSV exports in `powerbi/export` open directly in Excel; `data/outputs` forecast tables |
| Financial modeling and forecasting | `forecast.py`: backtest, interval, FY projection vs budget; completion/IBNR |
| Dashboards for emerging trends | `reports/partd_dashboard.html`, `app/streamlit_app.py`, trend drivers and top movers |
| Python | generator, benefit engine, forecast, charts, 25 pytest tests |
| Power BI | `powerbi/` DAX, theme, relationships and page guide (no .pbix) |
| Communication and storytelling | Auto-written insights on the dashboard; `INTERVIEW_GUIDE.md` |
| Streamline processes | One command rebuild (`make all`), CI, dbt tests replacing manual reconciliation |
| Work with real public data | `public_cms.py`, `public_extra.py`: spending, enrollment, state and negotiated-price data, reconciliation checks, tests |
| Excel | `reports/partd_analyst_pack.xlsx`: 7 sheets, about 1,300 live formulas, inputs in blue, assumption cells in yellow |
| Streamline processes | `docs/RUNBOOK.md`, `make public/excel/briefing`, automated cross-file checks |
