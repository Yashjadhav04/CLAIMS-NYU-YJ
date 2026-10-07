# Interview guide (four 30-minute conversations)

Open every conversation with one honest line: the data is synthetic, built to practice the work, not UHG data.

## VP: the business point (5 minutes)
- 2026 is tracking +6.7% over budget on net plan liability, about $1.2M for the year.
- GLP-1 brands and price drive it, and more members reach the out-of-pocket cap each year.
- The risk is in the forecast bias: my method has under-forecast, so the year may land higher.
Ask: what decisions does Part D leadership make from trend monitoring, and how often?

## Director: process and trust
- One command rebuilds everything; 86 automated checks catch reconciliation breaks.
- Rejected PDE submissions are tracked with dollars at risk, so data quality is a number, not a feeling.
- Story to tell: the March 2026 705-edit spike and how the dashboard surfaces it.
Ask: where does manual reconciliation still cost the team the most time?

## Manager: how I work with the team
- Built to be handed over: README, metric definitions, assumptions, tests.
- Flagged what I did not verify (SAS not run, no .pbix) rather than hiding it.
Ask: what does a first 90 days look like for this role?

## Senior Actuarial Analyst: depth
Be ready to explain:
- Final action: latest accepted record, adjustments replace, deletions remove, rejects excluded.
- Completion factors and why the latest month is an estimate.
- Why forecasting fits only 2025+ (the redesign), and why the backtest has few points.
- Price/volume/mix algebra and why net-plan "price" absorbs benefit design.
- The bug story: phase re-derivation failed on 91 claims because earlier claims were missing; the fix was to scope tests to complete history, not to loosen them.
- What I would add with real data: DIR and rebates, risk adjustment, CMS reinsurance reconciliation, bid-to-actual by segment.
Ask: how does the team reconcile PDE to payment today, and what breaks most?

## Questions to expect
- Why DuckDB and dbt? Fast to run anywhere, and the SQL ports to SQL Server or Teradata.
- Why not a bigger model? Twenty monthly points do not support it; baselines won or were close.
- Can I use SAS? Yes; the translations are written but unrun, and I would validate against the SQL oracle.

## Real-data talking points (CMS public data)
- National gross cost per member per month: $341 (2020) to $442 (2024), flat in 2024. Real enrollment is the denominator.
- Why 2024 was flat: cost per claim fell (insulin list-price cuts explain about $8B of a $29B negative price effect; the rest is unexplained) while claims per member rose.
- The ten negotiated drugs were 21% of 2024 spend ($61B). Q1 2026 spend per claim is already 40 to 70% lower for most of them. Be ready to say NovoLog is the exception (its list price was cut in 2024) and that this checks direction, not savings.
- You can say what you could not do: net cost needs rebates, which are not public; plan-level cost needs plan data.
- If asked how you check your work: cross-file reconciliation (0.04% gap between two CMS files), exact-sum identities, and a workbook where every derived number is a formula.
