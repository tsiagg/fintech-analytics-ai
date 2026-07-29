select 
    affiliate_id,
    country_code,
    tier,
    acquisition_cost
from {{ source('src_public', 'affiliates') }}