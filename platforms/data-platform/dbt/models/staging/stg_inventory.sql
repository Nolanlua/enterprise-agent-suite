{{ config(tags=["retail"]) }}

select
    store_id,
    sku,
    on_hand,
    in_transit,
    safety_stock,
    cast(snapshot_date as date) as snapshot_date
from {{ source('raw', 'inventory_snapshot') }}
qualify row_number() over (
    partition by store_id, sku
    order by snapshot_date desc
) = 1
