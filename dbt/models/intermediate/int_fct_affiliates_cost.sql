--affiliate cost - we pay acquisition cost to the affiliate on the first trade date of a client
with
cte_first_trade_date as (
select t.user_id, min(date(t.trade_ts)) as first_trade_date 
from {{ref('stg_public_trades')}} as t
group by t.user_id
)


select ftd.first_trade_date as effective_date,
       u.affiliate_id,
       aff.country_code as affiliate_country_code,
       ftd.user_id as user_id_acquired,
       u.country_code as user_country_code,
       aff.tier as affiliate_tier,
       aff.acquisition_cost/100 as acquisition_cost_usd       
from cte_first_trade_date as ftd
left join {{ref('stg_public_users')}} as u
    on ftd.user_id = u.user_id
left join {{ref('stg_public_affiliates')}} as aff
    on u.affiliate_id = aff.affiliate_id
where u.affiliate_id is not null --include only users connected to an affiliate