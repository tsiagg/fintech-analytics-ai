with cte_daily_agg as (
    select
        user_id,
        min(effective_date) as first_activity_date,
        max(effective_date) as last_activity_date,
        count(distinct effective_date) as days_with_any_activity,
        sum(daily_trade_revenue_usd) as lifetime_trade_revenue_usd,
        sum(daily_trade_revenue_usd - affiliate_cost_usd) as lifetime_net_trade_revenue_usd,
        sum(daily_gross_deposit_usd) as lifetime_gross_deposit_usd,
        sum(daily_withdrawal_usd) as lifetime_withdrawal_usd,
        sum(daily_net_deposit_usd) as lifetime_net_deposit_usd,
        sum(affiliate_cost_usd) as lifetime_affiliate_cost_usd
    from {{ ref('int_fct_daily_user_activity') }}
    group by user_id
),

cte_trade_stats as (
    select
        user_id,
        count(*) as lifetime_trade_count,
        count(distinct effective_date) as days_with_trades,
        min(effective_date) as first_trade_date,
        max(effective_date) as last_trade_date
    from {{ ref('int_fct_daily_trading') }}
    group by user_id
)

select
    du.user_id,
    du.signup_date,
    du.user_group,
    du.acquisition_channel,
    du.country_name,
    du.region,
    ts.first_trade_date,
    ts.last_trade_date,
    da.first_activity_date,
    da.last_activity_date,
    coalesce(ts.days_with_trades, 0) as days_with_trades,
    coalesce(da.days_with_any_activity, 0) as days_with_any_activity,
    coalesce(ts.lifetime_trade_count, 0) as lifetime_trade_count,
    coalesce(da.lifetime_trade_revenue_usd, 0.0) as lifetime_trade_revenue_usd,
    coalesce(da.lifetime_net_trade_revenue_usd, 0.0) as lifetime_net_trade_revenue_usd,
    coalesce(da.lifetime_gross_deposit_usd, 0.0) as lifetime_gross_deposit_usd,
    coalesce(da.lifetime_withdrawal_usd, 0.0) as lifetime_withdrawal_usd,
    coalesce(da.lifetime_net_deposit_usd, 0.0) as lifetime_net_deposit_usd,
    coalesce(da.lifetime_affiliate_cost_usd, 0.0) as lifetime_affiliate_cost_usd
from {{ ref('int_dim_users') }} as du
left join cte_daily_agg as da
    on du.user_id = da.user_id
left join cte_trade_stats as ts
    on du.user_id = ts.user_id
