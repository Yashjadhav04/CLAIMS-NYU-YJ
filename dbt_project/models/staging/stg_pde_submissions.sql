select
    pde_id,
    claim_group_id,
    member_id,
    drug_id,
    pharmacy_id,
    cast(fill_date as date) as fill_date,
    cast(days_supply as integer) as days_supply,
    quantity_dispensed,
    ingredient_cost,
    dispensing_fee,
    gdcb,
    gdca,
    gdcb + gdca as gross_drug_cost,
    patient_pay_amt,
    lics_amt,
    cpp_amt,
    mfr_discount_amt,
    adjustment_deletion_code,  -- '' original, 'A' adjustment, 'D' deletion
    dcs_status,                -- 'A' accepted, 'R' rejected by CMS edits
    nullif(edit_code, '') as edit_code,
    cast(received_date as date) as received_date
from {{ source('raw', 'pde_submissions') }}
