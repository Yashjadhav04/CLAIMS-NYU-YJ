# SAS reference translations

The role asks for SAS. These four programs mirror the dbt/SQL logic in SAS: final action, PMPM, price-volume-mix, reject rates.

**Honest status:** none of this was executed. No SAS licence was available when the repo was built. The dbt/DuckDB version is the tested one; use it as the oracle. If you run these, compare their outputs to `data/outputs` and the marts. The PVM macro mirrors the algebra in `mart_trend_drivers.sql`, which is the tested version.

Column names match `data/raw/*.csv`.
