select 
    withdrawal_id,
    user_id,
    amount,
    status,
    payment_provider,
    withdrawal_ts,
    batch_date
from {{ source('src_public', 'withdrawals') }}