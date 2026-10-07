# Part D Cost Trend Monitor

A production-style analytics project for a Medicare Part D actuarial analytics team: pharmacy claims (PDE) in, trusted PMPM and trend answers out, with a forecast, a dashboard, and tests that make the numbers defensible.

**Two dashboards, kept separate on purpose.**
- `reports/partd_dashboard.html`: **synthetic** plan-level claims (PDE, PMPM, IBNR, budget, forecast). Generated here. Nothing comes from UnitedHealth Group or any real plan, and the benefit parameters are illustrative (verify against the CMS Rate Announcement before any real use).
- `reports/partd_public_cms_dashboard.html`: **real public data** from data.cms.gov: spending by drug 2020 to 2024, monthly enrollment (real member months, so real PMPM), state-level cost, and the 2026 Medicare negotiated prices. All of Part D, gross cost before rebates. Run `make public` to download and build it.
- `reports/partd_analyst_pack.xlsx`: the same analysis as an Excel workbook with live formulas (`make excel`). `docs/BRIEFING.md`: the one-page memo (`make briefing`).

![synthetic dashboard](docs/dashboard.png)
![public CMS dashboard](docs/public_dashboard.png)

## The question it answers

> Are we running above or below budget on net plan liability, why, and where will the year land?

On the bundled synthetic book (6,000 members, 498K claims, Jan 2024 to Sep 2026):

- Projected 2026 net plan liability is **$19.7M vs a $18.4M budget (+6.7%, range +5.9% to +7.6%)**.
- Gross PMPM is up **11.3% year over year**: price +$22.6, mix +$19.4, utilization +$10.4, led by the GLP-1 brands.
- Catastrophic penetration is **15.6%** of members vs 12.8% a year earlier, which drives late-year liability under the out-of-pocket cap.
- PDE rejections spiked to **6.7% in March 2026** (edit 705), leaving **$71K** of gross cost unresolved.

## What is in the box

| Layer | What | Where |
|---|---|---|
| Data | Synthetic PDE stream: adjustments, deletions, rejects, resubmissions, late arrivals, 2024 legacy and 2025+ IRA benefit designs | `src/partd/generate.py`, `benefit.py` |
| Warehouse | DuckDB + dbt: staging, PDE final action, benefit-phase re-derivation, 14 marts, 13 singular tests | `dbt_project/` |
| Actuarial | Completion factors and IBNR, PMPM, budget variance, price/volume/mix with an exact-sum identity | marts `mart_pmpm_completed`, `mart_trend_drivers` |
| Forecast | Rolling-origin backtest, method chosen by backtest, empirical interval, FY projection vs budget | `src/partd/forecast.py` |
| Real public data | CMS spending, enrollment, state and negotiated-price data: national PMPM, use vs price split, state comparison, 2026 negotiation exposure, cross-file checks | `src/partd/public_cms.py`, `public_extra.py` |
| Analyst deliverables | Excel pack with live formulas, one-page briefing, quarterly runbook, data-quality log, public-data SQL and SAS | `reports/`, `docs/`, `sql/public/`, `sas/05_*` |
| Reporting | Standalone HTML dashboard, Streamlit app, Power BI kit (DAX, theme, build guide) | `reports/`, `app/`, `powerbi/` |
| SAS and SQL | SAS reference translations, ad-hoc SQL queries | `sas/`, `sql/` |
| Quality | 86 dbt checks (mutation-tested) and 40 pytest tests | `dbt_project/tests`, `tests/` |

## Run it

```bash
pip install -r requirements.txt
make all                 # generate -> load -> dbt build -> forecast -> report -> export -> test
open reports/partd_dashboard.html
make app                 # interactive Streamlit version
```

`PARTD_MEMBERS=800 make all` builds a small version in under a minute. CI does exactly that.

## Why you can trust the numbers

- **Money identity** on every claim: gross = patient pay + LICS + plan paid + manufacturer discount, to the cent.
- **Independent re-derivation.** The generator adjudicates claims; dbt re-derives each claim's benefit phase from cumulative cost and checks it (deductible pays nothing, cap respected, catastrophic member pays nothing).
- **Mutation-tested tests.** I corrupted the data in several ways and confirmed the tests fail.
- **Exact decomposition.** Utilization + mix + price equals the PMPM change, enforced by a test.
- **Backtest, not hope.** The forecast method is chosen by rolling-origin error against a naive baseline.

## Honest limitations

- Synthetic data; illustrative benefit parameters; the budget is synthetic too.
- Simplified benefit: the deductible applies to all tiers; adjustments are generated only on plan-only claims; the completion factor is gross-based and applied uniformly.
- The backtest has 9 forecasts, so the model choice and interval are tentative. The chosen method under-forecast every time (bias +2.0%), so the FY projection is more likely light than heavy.
- Benefit phase re-derivation is valid only when a member's claim history is complete, so tests are scoped accordingly.
- 2027 is not modeled.
- The public CMS data has no rebates, so everything on it is gross cost; net cost to a plan is not knowable from it. Per-member figures use CMS's separate enrollment file as the denominator. 2025 comes from CMS's preliminary quarterly file and is not compared with the annual series; injectable dose-unit prices (insulin, GLP-1s) are only partly reliable.
- SAS programs are reference translations and were **not run**. A `.pbix` is not included (cannot be built here); `powerbi/model.md` is the build guide and the DAX is untested in Desktop.

See `docs/` for architecture, metric definitions, assumptions, and an interview guide.
