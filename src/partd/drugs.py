"""Synthetic drug reference table.

Drug names are used only so the demo reads naturally to a pharmacy audience. Prices, prevalence and launch dates
are INVENTED for simulation; they are not real list prices, real market shares or real utilization.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

# (generic_name, brand_name, therapeutic_class, tier, kind, price_per_30_days, prevalence, units_per_day)
# kind: generic | brand | growth (brand with a utilization ramp over the window) | specialty
_DRUGS: list[tuple] = [
    # ---- generics
    ("atorvastatin", None, "Statin", 1, "generic", 9, 0.32, 1),
    ("rosuvastatin", None, "Statin", 1, "generic", 12, 0.12, 1),
    ("simvastatin", None, "Statin", 1, "generic", 6, 0.10, 1),
    ("lisinopril", None, "ACE inhibitor", 1, "generic", 5, 0.22, 1),
    ("losartan", None, "ARB", 1, "generic", 8, 0.14, 1),
    ("amlodipine", None, "Calcium channel blocker", 1, "generic", 5, 0.22, 1),
    ("metoprolol succinate", None, "Beta blocker", 2, "generic", 10, 0.13, 1),
    ("carvedilol", None, "Beta blocker", 1, "generic", 9, 0.07, 2),
    ("hydrochlorothiazide", None, "Diuretic", 1, "generic", 4, 0.12, 1),
    ("furosemide", None, "Diuretic", 1, "generic", 5, 0.09, 1),
    ("metformin", None, "Biguanide", 1, "generic", 6, 0.20, 2),
    ("glipizide", None, "Sulfonylurea", 1, "generic", 5, 0.07, 1),
    ("levothyroxine", None, "Thyroid", 2, "generic", 11, 0.22, 1),
    ("omeprazole", None, "Proton pump inhibitor", 1, "generic", 7, 0.15, 1),
    ("pantoprazole", None, "Proton pump inhibitor", 2, "generic", 9, 0.12, 1),
    ("sertraline", None, "SSRI", 1, "generic", 8, 0.09, 1),
    ("escitalopram", None, "SSRI", 1, "generic", 8, 0.08, 1),
    ("trazodone", None, "Antidepressant", 1, "generic", 6, 0.07, 1),
    ("gabapentin", None, "Anticonvulsant", 2, "generic", 10, 0.10, 3),
    ("tamsulosin", None, "BPH agent", 2, "generic", 10, 0.09, 1),
    ("clopidogrel", None, "Antiplatelet", 2, "generic", 9, 0.06, 1),
    ("warfarin", None, "Anticoagulant", 2, "generic", 6, 0.04, 1),
    ("potassium chloride", None, "Electrolyte", 2, "generic", 8, 0.05, 2),
    ("montelukast", None, "Leukotriene modifier", 2, "generic", 9, 0.06, 1),
    ("donepezil", None, "Dementia agent", 2, "generic", 12, 0.04, 1),
    ("alendronate", None, "Osteoporosis agent", 2, "generic", 7, 0.05, 1),
    ("allopurinol", None, "Gout agent", 1, "generic", 6, 0.06, 1),
    ("prednisone", None, "Corticosteroid", 1, "generic", 5, 0.05, 1),
    # ---- brands
    ("apixaban", "Eliquis", "Anticoagulant", 3, "brand", 590, 0.075, 2),
    ("rivaroxaban", "Xarelto", "Anticoagulant", 3, "brand", 560, 0.040, 1),
    ("empagliflozin", "Jardiance", "SGLT2 inhibitor", 3, "brand", 600, 0.065, 1),
    ("dapagliflozin", "Farxiga", "SGLT2 inhibitor", 3, "brand", 570, 0.040, 1),
    ("sitagliptin", "Januvia", "DPP-4 inhibitor", 3, "brand", 540, 0.040, 1),
    ("sacubitril/valsartan", "Entresto", "Heart failure agent", 3, "brand", 620, 0.022, 2),
    ("insulin glargine", "Lantus", "Insulin", 3, "brand", 280, 0.045, 1),
    ("fluticasone/umeclidinium/vilanterol", "Trelegy Ellipta", "COPD / asthma", 3, "brand", 600, 0.028, 1),
    ("tiotropium", "Spiriva", "COPD / asthma", 3, "brand", 500, 0.028, 1),
    ("linaclotide", "Linzess", "GI agent", 4, "brand", 480, 0.016, 1),
    ("mirabegron", "Myrbetriq", "Overactive bladder", 4, "brand", 520, 0.016, 1),
    # ---- growth brands (utilization ramps through the window; scenario for the demo)
    ("semaglutide", "Ozempic", "GLP-1 agonist", 3, "growth", 1000, 0.030, 1),
    ("dulaglutide", "Trulicity", "GLP-1 agonist", 3, "growth", 1020, 0.014, 1),
    ("tirzepatide", "Mounjaro", "GLP-1 / GIP agonist", 3, "growth", 1050, 0.016, 1),
    # ---- specialty
    ("adalimumab", "Humira", "Immunology", 5, "specialty", 6900, 0.0020, 1),
    ("etanercept", "Enbrel", "Immunology", 5, "specialty", 7200, 0.0012, 1),
    ("ustekinumab", "Stelara", "Immunology", 5, "specialty", 11500, 0.0010, 1),
    ("lenalidomide", "Revlimid", "Oncology", 5, "specialty", 17000, 0.0008, 1),
    ("ibrutinib", "Imbruvica", "Oncology", 5, "specialty", 16000, 0.0007, 1),
    ("palbociclib", "Ibrance", "Oncology", 5, "specialty", 15500, 0.0007, 1),
    ("osimertinib", "Tagrisso", "Oncology", 5, "specialty", 17000, 0.0005, 1),
    ("enzalutamide", "Xtandi", "Oncology", 5, "specialty", 13500, 0.0008, 1),
    ("bictegravir/emtricitabine/tenofovir", "Biktarvy", "HIV", 5, "specialty", 4200, 0.0010, 1),
]

# synthetic launch dates (the tirzepatide-like product launches inside the window so it shows up as a "new drug")
_LAUNCH = {"tirzepatide": date(2024, 6, 1)}

# annual probability that a member stops a therapy
ANNUAL_STOP_HAZARD = {"generic": 0.04, "brand": 0.08, "growth": 0.10, "specialty": 0.15}
# share of therapies filled as 90-day supplies
SHARE_90_DAY = {"generic": 0.32, "brand": 0.15, "growth": 0.10, "specialty": 0.0}


def build_drug_reference() -> pd.DataFrame:
    rows = []
    for i, (gname, brand, tclass, tier, kind, price30, prev, upd) in enumerate(_DRUGS, start=1):
        rows.append(
            {
                "drug_id": f"9{i:010d}",  # synthetic 11-digit NDC-like key, leading 9 = clearly not a real labeler
                "generic_name": gname,
                "brand_name": brand,
                "drug_label": brand or gname.title(),
                "therapeutic_class": tclass,
                "tier": tier,
                "kind": kind,
                "is_generic": kind == "generic",
                "is_specialty": kind == "specialty",
                "price_per_30_days": float(price30),
                "prevalence": float(prev),
                "units_per_day": int(upd),
                "launch_date": _LAUNCH.get(gname, date(2000, 1, 1)),
            }
        )
    return pd.DataFrame(rows)
