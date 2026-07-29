select 
    trade_id,
    user_id,
    symbol,
    volume_lots,
    pnl,
    trade_ts,
    batch_date
from {{ source('src_public', 'trades') }}