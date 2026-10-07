# SAS reference translations

These programs mirror the dbt/SQL logic in SAS: final action, PMPM, price-volume-mix, reject rates.

**Status:** these programs have not been executed; no SAS licence was available during development. The dbt/DuckDB version is the tested one; it serves as the reference. If these programs are run, their outputs should be compared with `data/outputs` and the marts. The PVM macro mirrors the algebra in `mart_trend_drivers.sql`, which is the tested version.

Column names match `data/raw/*.csv`.
