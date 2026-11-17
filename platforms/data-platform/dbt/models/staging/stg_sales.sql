{{ config(tags=["retail"]) }}

-- Deduplicate at the grain the warehouse guarantees. Source retries can emit
-- the same store/SKU/day twice; downstream features must never double count.
select
    store_id,
    sku,
    cast(business_date as date) as business_date,
    sum(qty) as qty,
    max(promo_flag) as promo_flag,
    max(stockout_flag) as stockout_flag
from {{ source('raw', 'fact_sales') }}
group by 1, 2, 3
