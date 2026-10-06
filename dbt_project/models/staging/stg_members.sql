select
    member_id,
    birth_year,
    extract(year from cast('{{ var("as_of_date") }}' as date)) - birth_year as age,
    case
        when extract(year from cast('{{ var("as_of_date") }}' as date)) - birth_year < 65 then 'Under 65 (disabled)'
        when extract(year from cast('{{ var("as_of_date") }}' as date)) - birth_year < 75 then '65-74'
        when extract(year from cast('{{ var("as_of_date") }}' as date)) - birth_year < 85 then '75-84'
        else '85+'
    end as age_band,
    sex,
    state,
    risk_score,
    ltc_flag,
    is_disabled_entitlement
from {{ source('raw', 'members') }}
