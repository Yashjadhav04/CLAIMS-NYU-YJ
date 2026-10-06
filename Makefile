# Part D actuarial analytics pipeline.  `make all` rebuilds everything from synthetic data.
SHELL := /bin/bash
export PYTHONPATH := $(CURDIR)/src
export PARTD_DB ?= $(CURDIR)/data/partd.duckdb
DBT := dbt

.PHONY: all generate load dbt forecast report export test app clean
all: generate load dbt forecast report export test

generate:        ## synthetic PDE claims, members, pharmacies, budget
	python -m partd.generate
load:            ## raw files -> DuckDB raw schema
	python -m partd.load_raw
dbt:             ## staging, final action, marts, 13 data tests
	cd dbt_project && $(DBT) seed --profiles-dir . && $(DBT) build --profiles-dir .
forecast:        ## backtest and 3-month forecast, FY projection
	python -m partd.forecast
report:          ## standalone HTML dashboard
	python -m partd.report
export:          ## CSV and parquet for Power BI
	python -m partd.export_bi
test:
	python -m pytest -q
app:
	streamlit run app/streamlit_app.py
clean:
	rm -rf data/raw data/outputs data/partd.duckdb dbt_project/target dbt_project/logs reports powerbi/export
