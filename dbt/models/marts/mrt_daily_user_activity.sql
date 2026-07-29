select
    du.user_id,
    du.signup_date,
    du.user_group,
    du.acquisition_channel,
    du.country_name,
    du.region,
    f.effective_date,
    f.affiliate_cost_usd,
    f.daily_client_pnl_usd,
    f.daily_company_pnl_usd,
    f.daily_trade_cost_usd,
    f.daily_cashback_usd,
    f.daily_trade_revenue_usd,
    f.daily_trade_revenue_usd - f.affiliate_cost_usd as daily_net_trade_revenue_usd,
    f.daily_gross_deposit_usd,
    f.daily_withdrawal_usd,
    f.daily_net_deposit_usd
from {{ ref('int_fct_daily_user_activity') }} as f
inner join {{ ref('int_dim_users') }} as du
    on f.user_id = du.user_id
