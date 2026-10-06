select pharmacy_id, pharmacy_npi, pharmacy_type, state
from {{ source('raw', 'pharmacies') }}
