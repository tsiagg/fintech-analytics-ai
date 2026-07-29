--daily trading model as 
with cte_trades_cost_cashback as (
select date(t.trade_ts) as effective_date,
       t.trade_ts,
       t.trade_id,
       t.user_id,
       t.symbol,
       im.symbol_group,
       t.volume_lots,
       t.pnl as client_pnl_usd,
       t.pnl * (-1) as company_pnl_usd,
       t.volume_lots * im.symbol_trade_cost_per_lot as trade_cost_usd,
       COALESCE(t.volume_lots,0.0) * COALESCE(im.symbol_cashback_per_lot,0.0) as cashback_per_trade_usd
from {{ref('stg_public_trades')}} as t
left join {{ref('stg_seed_instrument_mapping')}} as im
    on t.symbol = im.symbol_name
),

cte_adjustedvip_cashback as (
select tcc.effective_date,
       tcc.trade_ts,
       tcc.trade_id,
       tcc.user_id,
       tcc.symbol,
       tcc.symbol_group,
       tcc.volume_lots,
       tcc.client_pnl_usd,
       tcc.company_pnl_usd,
       tcc.trade_cost_usd,
       case when u.vip_status = 'vip' and tcc.symbol_group = 'FX Majors' then tcc.cashback_per_trade_usd * 1.20
            when u.vip_status = 'vip' and tcc.symbol_group = 'Metals' then tcc.cashback_per_trade_usd * 1.15
            when u.vip_status = 'vip' and tcc.symbol_group = 'Crypto' then tcc.cashback_per_trade_usd * 1.10
            else tcc.cashback_per_trade_usd
       end as adjusted_cashback_per_trade_usd
from cte_trades_cost_cashback as tcc
left join {{ref('stg_public_users')}} as u
    on tcc.user_id = u.user_id
)

select avc.effective_date,
       avc.trade_id,
       avc.user_id,
       avc.symbol,
       avc.symbol_group,
       avc.volume_lots,
       avc.client_pnl_usd,
       avc.company_pnl_usd,
       avc.trade_cost_usd,
       avc.adjusted_cashback_per_trade_usd,
       avc.company_pnl_usd + avc.trade_cost_usd - avc.adjusted_cashback_per_trade_usd as trade_revenue_usd
from cte_adjustedvip_cashback as avc