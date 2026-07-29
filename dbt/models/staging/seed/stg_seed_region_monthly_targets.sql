select
    region,
    start_date,
    end_date,
    target_monthly_active_traders,
    target_monthly_net_trade_revenue_usd,
    target_monthly_gross_deposit_usd
from {{ ref('region_monthly_targets') }}
