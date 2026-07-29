select 
    user_id,
    signup_date,
    country_code,
    vip_status,
    affiliate_id
from {{ source('src_public', 'users') }}
