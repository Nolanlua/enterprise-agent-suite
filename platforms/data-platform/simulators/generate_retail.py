"""Generate deterministic retail data for local development and evaluation.

The generated data is synthetic but keeps the relationships that matter:
store/SKU hierarchy, weekday seasonality, promotions, stockouts, inventory and
supplier offers. A fixed seed makes regression tests reproducible.
"""
from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data" / "raw" / "retail"
OUT.mkdir(parents=True, exist_ok=True)

STORES = [f"S{index:02d}" for index in range(1, 9)]
CATEGORIES = ["饮料", "零食", "乳品", "日化", "粮油"]
SKUS = [f"SKU-{index:04d}" for index in range(1, 61)]
START = pd.Timestamp("2026-08-01")


def build_master() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = random.Random(42)
    sku_rows = []
    for index, sku in enumerate(SKUS):
        category = CATEGORIES[index % len(CATEGORIES)]
        sku_rows.append(
            {
                "sku": sku,
                "sku_name": f"{category}商品{index + 1:02d}",
                "category": category,
                "brand": f"品牌{index % 7 + 1}",
                "unit": "箱" if index % 3 == 0 else "件",
                "case_pack": [6, 12, 12, 24][index % 4],
                "moq": [12, 24, 24, 48][index % 4],
                "shelf_life_days": [180, 365, 270, 540][index % 4],
                "unit_price": round(rng.uniform(3.5, 28.0), 2),
            }
        )
    stores = pd.DataFrame(
        [
            {
                "store_id": store,
                "store_name": f"演示门店{store[-1]}",
                "region": ["华北", "华东", "华南", "西南"][int(store[-1]) % 4],
                "store_type": "标准超市" if int(store[-1]) % 2 else "社区店",
            }
            for store in STORES
        ]
    )
    promotions = pd.DataFrame(
        [
            {
                "promo_id": f"P{index:03d}",
                "store_id": STORES[index % len(STORES)],
                "sku": SKUS[index % len(SKUS)],
                "start_date": START + pd.Timedelta(days=20 + index * 3),
                "end_date": START + pd.Timedelta(days=23 + index * 3),
                "lift": round(1.3 + (index % 5) * 0.15, 2),
            }
            for index in range(18)
        ]
    )
    return pd.DataFrame(sku_rows), stores, promotions


def build_sales(sku_df: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(2026)
    rows = []
    for store_index, store in enumerate(STORES):
        for sku_index, sku in enumerate(SKUS):
            base = 6 + (sku_index % 12) * 1.8 + (store_index % 3) * 2
            for day_index in range(120):
                date = START + pd.Timedelta(days=day_index)
                weekday_factor = 1.25 if date.weekday() >= 5 else 1.0
                trend = 1.0 + day_index * 0.0015
                noise = float(rng.normal(1.0, 0.12))
                qty = max(0, int(round(base * weekday_factor * trend * noise)))
                promo = 0
                if store_index == 0 and sku_index % 17 == 0 and 80 <= day_index <= 84:
                    promo = 1
                    qty = int(round(qty * 1.5))
                # A stockout is a missing sale, not zero demand. The flag lets the
                # forecaster exclude these days instead of learning a false zero.
                stockout = int(rng.random() < 0.015)
                if stockout:
                    qty = 0
                rows.append(
                    {
                        "store_id": store,
                        "sku": sku,
                        "business_date": date.date().isoformat(),
                        "qty": qty,
                        "promo_flag": promo,
                        "stockout_flag": stockout,
                    }
                )
    return pd.DataFrame(rows)


def build_inventory(sku_df: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    rows = []
    for store in STORES:
        for _, sku_row in sku_df.iterrows():
            rows.append(
                {
                    "store_id": store,
                    "sku": sku_row["sku"],
                    "on_hand": int(rng.integers(0, 120)),
                    "in_transit": int(rng.integers(0, 60)),
                    "safety_stock": int(rng.integers(6, 30)),
                    "snapshot_date": "2026-11-30",
                }
            )
    return pd.DataFrame(rows)


def build_supplier_offers(sku_df: pd.DataFrame) -> pd.DataFrame:
    rng = random.Random(99)
    rows = []
    for _, sku_row in sku_df.iterrows():
        for supplier in ["WY", "NANJING-WY", "LOCAL-01"]:
            rows.append(
                {
                    "supplier_code": supplier,
                    "sku": sku_row["sku"],
                    "supplier_sku": f"{supplier}-{sku_row['sku']}",
                    "available_qty": int(rng.choice([0, 24, 48, 96, 240, 480])),
                    "unit_price": round(float(sku_row["unit_price"]) * rng.uniform(0.92, 1.08), 2),
                    "moq": int(sku_row["moq"]),
                    "case_pack": int(sku_row["case_pack"]),
                    "lead_time_days": int(rng.choice([1, 2, 3, 5, 7])),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    sku_df, stores, promotions = build_master()
    sales = build_sales(sku_df)
    inventory = build_inventory(sku_df)
    offers = build_supplier_offers(sku_df)

    sku_df.to_csv(OUT / "dim_sku.csv", index=False)
    stores.to_csv(OUT / "dim_store.csv", index=False)
    promotions.to_csv(OUT / "promotions.csv", index=False)
    sales.to_csv(OUT / "fact_sales.csv", index=False)
    inventory.to_csv(OUT / "inventory_snapshot.csv", index=False)
    offers.to_csv(OUT / "supplier_offers.csv", index=False)
    print(f"retail data written to {OUT}: sales={len(sales)} inventory={len(inventory)} offers={len(offers)}")


if __name__ == "__main__":
    main()
