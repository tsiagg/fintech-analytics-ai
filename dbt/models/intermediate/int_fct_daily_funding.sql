with 
cte_daily_sucess_deposits as (
select user_id,
       date(deposit_ts) as effective_date,
       sum(amount) as deposit_amount_usd
from {{ref('stg_public_deposits')}}
where status = 'completed'
group by date(deposit_ts), user_id
),

cte_daily_sucess_withdrawals as (
select date(withdrawal_ts) as effective_date,
       user_id,
       sum(amount) as withdrawal_amount_usd
from {{ref('stg_public_withdrawals')}}
where status = 'completed'
group by date(withdrawal_ts), user_id
)

select COALESCE(dsd.user_id, dsw.user_id) as user_id,
       COALESCE(dsd.effective_date, dsw.effective_date) as effective_date,
       COALESCE(dsd.deposit_amount_usd, 0.0) as gross_deposit_usd,
       COALESCE(dsw.withdrawal_amount_usd, 0.0) as withdrawal_usd,
       COALESCE(dsd.deposit_amount_usd, 0.0) - COALESCE(dsw.withdrawal_amount_usd, 0.0) as net_deposit_usd
from cte_daily_sucess_deposits as dsd
full outer join cte_daily_sucess_withdrawals as dsw
    on dsd.user_id = dsw.user_id
    and dsd.effective_date = dsw.effective_date