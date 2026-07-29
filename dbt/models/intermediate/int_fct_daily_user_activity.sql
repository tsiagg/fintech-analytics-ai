with cte_daily_trading as (
    select
        user_id,
        effective_date,
        sum(client_pnl_usd) as daily_client_pnl_usd,
        sum(company_pnl_usd) as daily_company_pnl_usd,
        sum(trade_cost_usd) as daily_trade_cost_usd,
        sum(adjusted_cashback_per_trade_usd) as daily_cashback_usd,
        sum(trade_revenue_usd) as daily_trade_revenue_usd
    from {{ ref('int_fct_daily_trading') }}
    group by user_id, effective_date
),

cte_daily_funding as (
    select
        user_id,
        effective_date,
        sum(gross_deposit_usd) as daily_gross_deposit_usd,
        sum(withdrawal_usd) as daily_withdrawal_usd,
        sum(net_deposit_usd) as daily_net_deposit_usd
    from {{ ref('int_fct_daily_funding') }}
    group by user_id, effective_date
),

cte_combined_daily_data as (
    select
        coalesce(dt.user_id, df.user_id) as user_id,
        coalesce(dt.effective_date, df.effective_date) as effective_date,
        coalesce(dt.daily_client_pnl_usd, 0.0) as daily_client_pnl_usd,
        coalesce(dt.daily_company_pnl_usd, 0.0) as daily_company_pnl_usd,
        coalesce(dt.daily_trade_cost_usd, 0.0) as daily_trade_cost_usd,
        coalesce(dt.daily_cashback_usd, 0.0) as daily_cashback_usd,
        coalesce(dt.daily_trade_revenue_usd, 0.0) as daily_trade_revenue_usd,
        coalesce(df.daily_gross_deposit_usd, 0.0) as daily_gross_deposit_usd,
        coalesce(df.daily_withdrawal_usd, 0.0) as daily_withdrawal_usd,
        coalesce(df.daily_net_deposit_usd, 0.0) as daily_net_deposit_usd
    from cte_daily_trading as dt
    full outer join cte_daily_funding as df
        on dt.user_id = df.user_id
        and dt.effective_date = df.effective_date
),

cte_add_affiliate_cost as (
    select
        dd.*,
        coalesce(ac.acquisition_cost_usd, 0.0) as affiliate_cost_usd
    from cte_combined_daily_data as dd
    left join {{ ref('int_fct_affiliates_cost') }} as ac
        on dd.user_id = ac.user_id_acquired
        and dd.effective_date = ac.effective_date
)

select
    user_id,
    effective_date,
    daily_client_pnl_usd,
    daily_company_pnl_usd,
    daily_trade_cost_usd,
    daily_cashback_usd,
    daily_trade_revenue_usd,
    daily_gross_deposit_usd,
    daily_withdrawal_usd,
    daily_net_deposit_usd,
    affiliate_cost_usd
from cte_add_affiliate_cost
