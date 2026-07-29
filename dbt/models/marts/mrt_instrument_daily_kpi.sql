select
    t.effective_date,
    du.region,
    t.symbol as symbol_name,
    im.symbol_nickname,
    im.symbol_group,
    count(distinct t.trade_id) as trade_count,
    count(distinct t.user_id) as active_traders,
    sum(t.volume_lots) as volume_lots,
    sum(t.client_pnl_usd) as client_pnl_usd,
    sum(t.company_pnl_usd) as company_pnl_usd,
    sum(t.trade_cost_usd) as trade_cost_usd,
    sum(t.adjusted_cashback_per_trade_usd) as cashback_usd,
    sum(t.trade_revenue_usd) as trade_revenue_usd
from {{ ref('int_fct_daily_trading') }} as t
inner join {{ ref('int_dim_users') }} as du
    on t.user_id = du.user_id
left join {{ ref('stg_seed_instrument_mapping') }} as im
    on t.symbol = im.symbol_name
group by
    t.effective_date,
    du.region,
    t.symbol,
    im.symbol_nickname,
    im.symbol_group
