{{ config(tags=["retail"], materialized="table") }}

with daily as (
    select * from {{ ref('fct_store_sku_daily') }}
),
latest as (
    select
        store_id,
        sku,
        max(business_date) as business_date
    from daily
    group by 1, 2
)
select
    d.store_id,
    d.sku,
    d.business_date,
    d.avg_qty_7d,
    d.avg_qty_28d,
    i.on_hand,
    i.in_transit,
    i.safety_stock,
    s.case_pack,
    s.moq,
    s.shelf_life_days,
    s.unit_price
from latest l
join daily d
  on l.store_id = d.store_id and l.sku = d.sku and l.business_date = d.business_date
join {{ ref('stg_inventory') }} i
  on i.store_id = d.store_id and i.sku = d.sku
join {{ source('raw', 'dim_sku') }} s
  on s.sku = d.sku
