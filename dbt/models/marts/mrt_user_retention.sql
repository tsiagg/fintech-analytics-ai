with cte_users as (
    select
        user_id,
        signup_date,
        user_group,
        acquisition_channel,
        country_name,
        region,
        date_trunc('week', signup_date)::date as cohort_period
    from {{ ref('int_dim_users') }}
),

cte_first_trade as (
    select
        user_id,
        min(effective_date) as first_trade_date
    from {{ ref('int_fct_daily_trading') }}
    group by user_id
),

cte_trading_days as (
    select distinct
        user_id,
        effective_date
    from {{ ref('int_fct_daily_trading') }}
),

cte_activity_days as (
    select distinct
        user_id,
        effective_date
    from {{ ref('int_fct_daily_user_activity') }}
),

cte_max_loaded_date as (
    select max(effective_date) as max_effective_date
    from {{ ref('int_fct_daily_user_activity') }}
),

cte_recent_activity as (
    select distinct
        ad.user_id
    from cte_activity_days as ad
    cross join cte_max_loaded_date as md
    where ad.effective_date > md.max_effective_date - interval '7 days'
        and ad.effective_date <= md.max_effective_date
)

select
    u.user_id,
    u.signup_date,
    u.user_group,
    u.acquisition_channel,
    u.country_name,
    u.region,
    u.cohort_period,
    (ft.first_trade_date - u.signup_date) as days_from_signup_to_first_trade,
    exists (
        select 1
        from cte_trading_days as td
        where td.user_id = u.user_id
            and td.effective_date = u.signup_date
    ) as is_trader_retained_day_0,
    exists (
        select 1
        from cte_trading_days as td
        where td.user_id = u.user_id
            and td.effective_date = u.signup_date + 1
    ) as is_trader_retained_day_1,
    exists (
        select 1
        from cte_trading_days as td
        where td.user_id = u.user_id
            and td.effective_date = u.signup_date + 7
    ) as is_trader_retained_day_7,
    exists (
        select 1
        from cte_trading_days as td
        where td.user_id = u.user_id
            and td.effective_date = u.signup_date + 30
    ) as is_trader_retained_day_30,
    exists (
        select 1
        from cte_activity_days as ad
        where ad.user_id = u.user_id
            and ad.effective_date = u.signup_date
    ) as is_active_retained_day_0,
    exists (
        select 1
        from cte_activity_days as ad
        where ad.user_id = u.user_id
            and ad.effective_date = u.signup_date + 1
    ) as is_active_retained_day_1,
    exists (
        select 1
        from cte_activity_days as ad
        where ad.user_id = u.user_id
            and ad.effective_date = u.signup_date + 7
    ) as is_active_retained_day_7,
    exists (
        select 1
        from cte_activity_days as ad
        where ad.user_id = u.user_id
            and ad.effective_date = u.signup_date + 30
    ) as is_active_retained_day_30,
    ra.user_id is not null as is_active_last_7d
from cte_users as u
left join cte_first_trade as ft
    on u.user_id = ft.user_id
left join cte_recent_activity as ra
    on u.user_id = ra.user_id
