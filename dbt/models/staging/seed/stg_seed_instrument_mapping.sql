select
    symbol_name,
    symbol_nickname,
    symbol_group,
    symbol_trade_cost_per_lot,
    symbol_cashback_per_lot,
    symbol_size
from {{ ref('instrument_mapping') }}
