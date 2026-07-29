with 
cte_region_daily_revenue as (
select
    du.region,
    date(date_trunc('month',f.effective_date)) as effective_month,
    count(distinct f.user_id) as active_users,
    sum(f.daily_trade_revenue_usd - f.affiliate_cost_usd) as daily_net_trade_revenue_usd,
    sum(f.daily_gross_deposit_usd) as gross_deposit_usd
from {{ ref('int_fct_daily_user_activity') }} as f 
left join {{ ref('int_dim_users') }} as du
    on f.user_id = du.user_id
group by du.region,  date(date_trunc('month',f.effective_date))
)

select  de.region,
        de.effective_month,
        de.active_users as actual_active_users,
        ts.target_monthly_active_traders as target_active_users,
        de.daily_net_trade_revenue_usd as actual_net_trade_revenue_usd,
        ts.target_monthly_net_trade_revenue_usd as target_net_trade_revenue_usd,
        de.gross_deposit_usd as actual_gross_deposit_usd,
        ts.target_monthly_gross_deposit_usd as target_gross_deposit_usd
from cte_region_daily_revenue as de 
left join {{ ref('stg_seed_region_monthly_targets') }} as ts
    on de.region = ts.region
    and de.effective_month between ts.start_date and ts.end_date