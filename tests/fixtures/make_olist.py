import csv
from datetime import date, timedelta
from pathlib import Path

AS_OF = date(2018, 3, 15)
START = date(2018, 1, 30)
SELLER_ID = "seller_demo"

SKUS = {
    "sku_profit_erosion": ("cool_stuff", "100.00"),
    "sku_ad_inefficiency": ("watches_gifts", "80.00"),
    "sku_stockout_risk": ("health_beauty", "50.00"),
    "sku_excess_inventory": ("bed_bath_table", "40.00"),
    "sku_healthy": ("cool_stuff", "60.00"),
}


def _units(sku_id: str, day: date) -> int:
    idx = (day - START).days
    if sku_id == "sku_profit_erosion":
        return 12 if idx >= 38 else 10
    if sku_id == "sku_ad_inefficiency":
        return 8
    if sku_id == "sku_stockout_risk":
        return 10
    if sku_id == "sku_excess_inventory":
        return 4 if idx >= 38 else 12
    return 8


def write_mini_olist(dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    orders_path = dest / "olist_orders_dataset.csv"
    items_path = dest / "olist_order_items_dataset.csv"
    products_path = dest / "olist_products_dataset.csv"
    reviews_path = dest / "olist_order_reviews_dataset.csv"
    sellers_path = dest / "olist_sellers_dataset.csv"

    with products_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "product_id",
                "product_category_name",
                "product_name_lenght",
                "product_description_lenght",
                "product_photos_qty",
                "product_weight_g",
                "product_length_cm",
                "product_height_cm",
                "product_width_cm",
            ]
        )
        for sku_id, (category, _) in SKUS.items():
            w.writerow([sku_id, category, 10, 20, 1, 500, 20, 10, 15])

    with sellers_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"])
        w.writerow([SELLER_ID, "01000", "sao paulo", "SP"])

    order_rows: list[list[str]] = []
    item_rows: list[list[str]] = []
    review_rows: list[list[str]] = []
    day = START
    while day <= AS_OF:
        ts = f"{day.isoformat()} 12:00:00"
        for sku_id, (_, price) in SKUS.items():
            for i in range(_units(sku_id, day)):
                order_id = f"ord_{sku_id}_{day.isoformat()}_{i}"
                order_rows.append(
                    [order_id, "cust_1", "delivered", ts, ts, ts, ts, ts]
                )
                item_rows.append(
                    [order_id, "1", sku_id, SELLER_ID, ts, price, "10.00"]
                )
                recent = (AS_OF - day).days <= 6
                score = "1" if sku_id == "sku_profit_erosion" and recent else "5"
                review_rows.append([f"rev_{order_id}", order_id, score, "", "", ts, ts])
        day += timedelta(days=1)

    with orders_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "order_id",
                "customer_id",
                "order_status",
                "order_purchase_timestamp",
                "order_approved_at",
                "order_delivered_carrier_date",
                "order_delivered_customer_date",
                "order_estimated_delivery_date",
            ]
        )
        w.writerows(order_rows)

    with items_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "order_id",
                "order_item_id",
                "product_id",
                "seller_id",
                "shipping_limit_date",
                "price",
                "freight_value",
            ]
        )
        w.writerows(item_rows)

    with reviews_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "review_id",
                "order_id",
                "review_score",
                "review_comment_title",
                "review_comment_message",
                "review_creation_date",
                "review_answer_timestamp",
            ]
        )
        w.writerows(review_rows)
    return dest
