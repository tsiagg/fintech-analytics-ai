{{ config(
    materialized='table',
    tags=['serving', 'streamlit_dashboard']
) }}

with daily as (
    select
        effective_date,
        count(distinct user_id) as active_users,
        sum(daily_trade_revenue_usd) as gross_revenue_usd,
        sum(daily_net_trade_revenue_usd) as net_revenue_usd,
        sum(daily_gross_deposit_usd) as gross_deposits_usd,
        sum(daily_withdrawal_usd) as withdrawals_usd,
        sum(daily_net_deposit_usd) as net_flow_usd,
        case
            when sum(daily_gross_deposit_usd) > 0
                then sum(daily_withdrawal_usd) / sum(daily_gross_deposit_usd)
            else null
        end as withdrawal_ratio
    from {{ ref('mrt_daily_user_activity') }}
    group by effective_date
),

-- New users by signup day, independent of whether they traded/funded that day
-- (so a signup-only day is still counted). Joined onto the activity spine.
new_users as (
    select
        signup_date as effective_date,
        count(distinct user_id) as new_users
    from {{ ref('int_dim_users') }}
    group by signup_date
)

select
    d.effective_date,
    d.active_users,
    coalesce(nu.new_users, 0) as new_users,
    d.gross_revenue_usd,
    d.net_revenue_usd,
    d.gross_deposits_usd,
    d.withdrawals_usd,
    d.net_flow_usd,
    d.withdrawal_ratio,
    d.net_revenue_usd / nullif(d.active_users, 0) as net_revenue_per_user_usd,
    d.gross_deposits_usd / nullif(d.active_users, 0) as gross_deposit_per_user_usd
from daily as d
left join new_users as nu
    on nu.effective_date = d.effective_date
