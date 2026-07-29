{{
    config(
        materialized='table',
    )
}}

/*
  Day-level calendar for MetricFlow / dbt semantic layer.
  Range is controlled by vars in dbt_project.yml (inclusive start, exclusive end).
*/

with days as (
    {{
        dbt.date_spine(
            'day',
            "cast('" ~ var('metricflow_time_spine_start') ~ "' as date)",
            "cast('" ~ var('metricflow_time_spine_end') ~ "' as date)"
        )
    }}
),

final as (
    select cast(date_day as date) as date_day
    from days
    where date_day >= cast('{{ var("metricflow_time_spine_start") }}' as date)
        and date_day < cast('{{ var("metricflow_time_spine_end") }}' as date)
)

select * from final
