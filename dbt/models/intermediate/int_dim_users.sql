select
    u.user_id,
    u.signup_date,
    u.country_code,
    coalesce(u.vip_status, 'normal') as user_group,
    case when u.affiliate_id is not null then 'Affiliate' else 'Direct' end as acquisition_channel,
    u.affiliate_id,
    cc.country_name,
    cc.region
from {{ ref('stg_public_users') }} as u
left join {{ ref('stg_seed_country_codes') }} as cc
    on u.country_code = cc.country_code
