{{ config(
    materialized='table',
    tags=['serving', 'streamlit_dashboard']
) }}

select
    effective_date,
    country_name,
    region,
    sum(daily_trade_revenue_usd) as gross_revenue_usd
from {{ ref('mrt_daily_user_activity') }}
group by effective_date, country_name, region
