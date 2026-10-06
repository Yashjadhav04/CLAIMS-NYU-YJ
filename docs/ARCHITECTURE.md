# Architecture

```mermaid
flowchart LR
  G[generate.py<br/>synthetic members, fills, PDE stream] --> R[(raw files)]
  B[benefit_params.csv<br/>shared seed] --> G
  B --> D
  R --> L[load_raw.py] --> W[(DuckDB raw schema)]
  W --> S[dbt staging]
  S --> F[int_pde_final_action<br/>latest accepted record, drop deletions]
  F --> C[fct_pde_claims<br/>benefit phase re-derived]
  C --> M[marts: PMPM, completion, budget variance,<br/>trend drivers, edits, penetration, concentration]
  M --> FC[forecast.py<br/>backtest, projection]
  M --> V[report.py / Streamlit / Power BI export]
  FC --> V
  D[dbt tests] -.guard.-> C
  D -.guard.-> M
```

## Design decisions

1. **Single source of truth for benefit design.** `benefit_params.csv` is read by both the Python generator and dbt, so the two cannot drift.
2. **Final action before anything else.** PDE records are a stream of originals, adjustments and deletions. Everything downstream uses only the latest accepted record per claim.
3. **Completion before trend.** Recent months are incomplete. Trend and forecast use completion-adjusted figures; the latest month is flagged.
4. **Regime break.** The 2025 redesign changes the level and shape of liability, so forecasting uses 2025 onward only.
5. **Independent check, not a copy.** dbt re-derives phase from cumulative amounts instead of trusting the generator's labels.
6. **Marts at segment grain** (month x plan type x LIS) so any dashboard can aggregate without re-deriving ratios.
