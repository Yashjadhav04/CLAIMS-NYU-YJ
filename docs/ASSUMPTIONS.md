# Assumptions and limits

## Data
- Synthetic. Seeded and reproducible (`PARTD_SEED`).
- Benefit parameters are illustrative; check the CMS Rate Announcement for real values.
- The budget is a synthetic bid: 2025 actual PMPM x 1.07, with seasonality.

## Simplifications
- Deductible applies to all tiers.
- Adjustments are generated only on plan-only (catastrophic) claims, as price reductions.
- Completion factor is based on gross cost and applied uniformly to all measures and segments.
- Reinsurance is a flat rate on GDCA by applicable/non-applicable drug, not CMS's actual reconciliation.
- No risk adjustment, no direct and indirect remuneration (DIR) or rebates, no low-income cost-sharing reconciliation, no Part D reinsurance true-up.
- 2027 benefit design is not modeled.

## Statistics
- The backtest has 9 forecasts. Method choice and interval width are tentative.
- The chosen method under-forecast on every origin (bias +2.0%), a sign of accelerating cost growth that seasonal-naive with trailing growth lags. Read the base FY projection as slightly light.
- Intervals are empirical (80th percentile of backtest absolute error, floor 2%), not model-based.

## Tests
- Benefit-phase re-derivation requires complete claim history. Tests use `claims_with_complete_history()`, which drops recent fills (within 95 days of extract) and member-years with unresolved rejects. That scoping is deliberate and documented, not a loophole.

## Public CMS data
- Source: data.cms.gov, Medicare Part D Spending by Drug (annual, 2020-2024) and Medicare Quarterly Part D Spending by Drug (2025 preliminary).
- Gross drug cost (Medicare + plan + beneficiary), before rebates. Aggregate for all of Part D, not one plan.
- Per-member figures divide the spending file by member months from CMS Monthly Enrollment (Part D enrollees summed over 12 months). Volume in the trend breakdown is CMS dose units; for injectables these can change with strength and packaging.
- The 2023-to-2024 price effect is negative (-$29B). Insulin explains about $8B; the rest is spread over ~2,700 drugs and is not attributed.
- 2025 (quarterly file) and Q1 2026 are not used for growth rates: CMS says the quarterly file is preliminary and not directly comparable.
- State comparison: cost by prescriber location over enrollees by residence; DC inflated; territories excluded.
- 2026 negotiated prices come from CMS's fact sheet; the exposure figure applies the announced cut to 2024 spend at constant volume, vs list price and before rebates. It is a ceiling for a gross view, not a forecast.
- Excel Net_Sensitivity uses an assumed rebate rate (yellow cell); CMS publishes no rebates.
