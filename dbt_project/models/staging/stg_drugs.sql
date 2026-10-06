select
    drug_id,
    generic_name,
    brand_name,
    drug_label,
    therapeutic_class,
    cast(tier as integer) as tier,
    kind as drug_kind,
    is_generic,
    is_specialty,
    not is_generic as is_applicable_drug,  -- brand / biosimilar: subject to the manufacturer discount program
    price_per_30_days,
    units_per_day
from {{ source('raw', 'drugs') }}
