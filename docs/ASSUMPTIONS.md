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
