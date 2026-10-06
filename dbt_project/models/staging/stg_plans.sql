select plan_id, contract_id, plan_type, plan_name
from {{ source('raw', 'plans') }}
