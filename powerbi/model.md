# Power BI model and build guide

A `.pbix` file cannot be generated from this repo's environment, so this folder gives you everything needed to build it in about 30 minutes. Nothing here was opened in Power BI Desktop; treat names as a starting point.

## 1. Load
1. Run `make export` (writes `powerbi/export/*.csv` and `*.parquet`).
2. Power BI Desktop > Get data > Folder (or Parquet) and load the tables below.
3. View > Themes > Browse for themes > `theme.json`.

## 2. Relationships (star schema, single direction, dim to fact)
| From (one) | To (many) |
|---|---|
| dim_date[date] | fact_pmpm_monthly[incurred_month] |
| dim_date[date] | fact_budget_variance[incurred_month] |
| dim_date[date] | fact_catastrophic_penetration[incurred_month] |
| dim_date[date] | fact_pde_edits[received_month] |

`fact_trend_drivers` has one row per measure and no date key; use it unrelated, filtered by the `measure` column.
`fact_trend_by_drug` and `fact_top_drugs_ytd` join to `dim_drug[drug_id]`.
Mark `dim_date` as the date table.

## 3. Measures
Paste `measures.dax` into a measures table.

## 4. Suggested pages
1. **Executive summary**: cards for Net Plan Liability YTD, Variance to Budget %, Net Plan PMPM YoY %; line of Net Plan PMPM vs budget; forecast table from `forecast_pmpm`.
2. **Trend drivers**: waterfall from `fact_trend_drivers` (utilization, mix, price); bar of top movers from `fact_trend_by_drug`.
3. **Benefit and members**: stacked column by payer (plan, reinsurance, manufacturer, LICS, member); catastrophic penetration line.
4. **Data quality**: reject rate by edit code; unresolved dollars.

Design rules used in the repo's own dashboard: one y axis per chart, thin lines, legend for 2+ series, direct labels on the latest point, and no dual axes.

## 5. Caveats
Latest months are completion-adjusted (IBNR). Say so on the page. All data is synthetic.
