{{ config(tags=["retail"], materialized="table") }}

with sales as (
    select * from {{ ref('stg_sales') }}
),
calendar as (
    select distinct business_date from sales
)
select
    store_id,
    sku,
    business_date,
    qty,
    promo_flag,
    stockout_flag,
    -- 7-day and 28-day rolling demand are defined once here and reused by the
    -- feature view. Agents never recompute these metrics from raw sales.
    avg(case when stockout_flag = 0 then qty end) over (
        partition by store_id, sku
        order by business_date
        rows between 6 preceding and current row
    ) as avg_qty_7d,
    avg(case when stockout_flag = 0 then qty end) over (
        partition by store_id, sku
        order by business_date
        rows between 27 preceding and current row
    ) as avg_qty_28d
from sales
