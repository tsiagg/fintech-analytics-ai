select 
    deposit_id,
    user_id,
    amount,
    status,
    payment_provider,
    deposit_ts,
    batch_date
from {{ source('src_public', 'deposits') }}