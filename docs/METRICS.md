# Metric definitions

| Metric | Definition |
|---|---|
| Gross drug cost | GDCB + GDCA from the final-action PDE record |
| Net plan liability | Covered plan paid minus estimated CMS reinsurance on GDCA (rates in `benefit_params.csv`) |
| Member months | Enrolled members counted per month from enrollment, not claims |
| PMPM | Dollars divided by member months |
| Completion factor | Share of a month's eventual gross cost received by a given development age, learned from mature months |
| Completion-adjusted | Reported value divided by completion factor (IBNR gross-up) |
| Budget variance | Actual completion-adjusted dollars minus budget PMPM x member months |
| Utilization effect | (U1/U0 - 1) x PMPM0, where U is days supply per member month |
| Mix effect (existing) | sum of (u1 - u0 x U1/U0) x p0 across drugs present in both periods |
| Mix effect (new drugs) | sum of u1 x p1 for drugs absent in the prior period |
| Price effect | sum of u1 x (p1 - p0) |
| Catastrophic penetration | Members whose cumulative TrOOP has reached the threshold / members enrolled |
| PDE reject rate | Rejected submissions / submissions, by received month and edit code |
| Unresolved rejects | Claims with rejected submissions and no accepted record; gross cost at risk |
| Cost concentration | Share of gross cost from the top 1%, 5%, 10% of members |

Utilization + mix + price = PMPM change, exactly (tested).
For net plan liability, "price" also absorbs benefit-design and cost-share effects, because it is net cost per day supply.
