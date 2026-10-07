# Data quality log (real CMS data)

| Check | Result on this build | Why it matters |
|---|---|---|
| 2024 spending file total vs prescriber-file national total | within 0.04% | Two CMS files describe the same program |
| Prescriber-file national total vs sum of states | within 0.2% | Small cells are suppressed in state rows |
| PDP + MA-PD enrollees = total enrollees | exact | Enrollment split is internally consistent |
| Drug rows with spend but zero claims (2024) | 0 | No impossible rows |
| Drug rows with CMS outlier flag (2024) | about 11% of rows | CMS flags unit-price outliers; they are kept, not dropped |
| No duplicate drug rows | pass | Joins would double-count otherwise |
| 50 states + DC cover national spend | about 98.7% | Rest is Puerto Rico and other territories, excluded on purpose |

## Issues found and how they were handled
- **2025 spending is not comparable to 2020 to 2024.** It comes from CMS's preliminary quarterly file; CMS warns against comparing it with the annual file. It is shown as one number and excluded from growth rates.
- **Enrollment columns arrive as text with suppression marks.** They are coerced to numbers; non-numeric cells become missing, and only complete 12-month years are used for PMPM.
- **Dose units are not comparable across drugs.** Volume in the trend breakdown is dose units; mix absorbs unit differences, and injectable unit prices are only partly reliable.
- **DC cost per member is inflated** because costs follow the prescriber's location and members live in neighboring states. Territories are excluded for the same reason.
- **The 2023 to 2024 price effect (-$29B) is only partly explained** (insulin about $8B). The rest is spread over ~2,700 drugs and not attributed.
- **Negotiated prices are typed in** from CMS's fact sheet (`src/partd/mfp_2026.csv`), not downloaded. Re-check against the source when it is updated.
