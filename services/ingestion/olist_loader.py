from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from domain.base import FrozenModel


class RawOrderLine(FrozenModel):
    order_id: str
    sku_id: str
    seller_id: str
    purchased_at: datetime
    price: Decimal
    freight_value: Decimal
    order_status: str
    category: str
    review_score: int | None = None


_VALID_STATUS = {"delivered", "shipped", "invoiced", "processing", "approved"}


def _find(data_dir: Path, *names: str) -> Path:
    for name in names:
        path = data_dir / name
        if path.exists():
            return path
    raise FileNotFoundError(f"missing {names} in {data_dir}")


def _ts(value: object, tz: ZoneInfo) -> datetime:
    parsed = pd.to_datetime(value)
    if parsed.tzinfo is None:
        return parsed.tz_localize(tz).to_pydatetime()
    return parsed.tz_convert(tz).to_pydatetime()


def _money(value: object) -> Decimal:
    if pd.isna(value):
        return Decimal("0")
    return Decimal(str(value))


def load_olist(
    data_dir: Path,
    tz: ZoneInfo,
    seller_id: str | None = None,
    top_sku_count: int = 50,
) -> list[RawOrderLine]:
    orders = pd.read_csv(_find(data_dir, "olist_orders_dataset.csv", "orders.csv"))
    items = pd.read_csv(_find(data_dir, "olist_order_items_dataset.csv", "order_items.csv"))
    products_path = data_dir / "olist_products_dataset.csv"
    if not products_path.exists():
        products_path = data_dir / "products.csv"
    products = pd.read_csv(products_path) if products_path.exists() else pd.DataFrame()
    reviews_path = data_dir / "olist_order_reviews_dataset.csv"
    if not reviews_path.exists():
        reviews_path = data_dir / "reviews.csv"
    reviews = pd.read_csv(reviews_path) if reviews_path.exists() else pd.DataFrame()

    merged = items.merge(orders, on="order_id", how="inner")
    if not products.empty and "product_id" in products.columns:
        cols = ["product_id"]
        if "product_category_name" in products.columns:
            cols.append("product_category_name")
        merged = merged.merge(products[cols], on="product_id", how="left")
    if not reviews.empty and "order_id" in reviews.columns:
        review_cols = ["order_id", "review_score"]
        review_part = reviews[review_cols].drop_duplicates("order_id")
        merged = merged.merge(review_part, on="order_id", how="left")
    else:
        merged["review_score"] = pd.NA

    merged["order_status"] = merged["order_status"].astype(str).str.lower()
    merged = merged[merged["order_status"].isin(_VALID_STATUS)]
    if seller_id:
        merged = merged[merged["seller_id"].astype(str) == seller_id]
    else:
        revenue_by_seller = merged.groupby("seller_id")["price"].sum().sort_values(ascending=False)
        if revenue_by_seller.empty:
            return []
        seller_id = str(revenue_by_seller.index[0])
        merged = merged[merged["seller_id"].astype(str) == seller_id]

    sku_revenue = merged.groupby("product_id")["price"].sum().sort_values(ascending=False)
    keep = set(sku_revenue.head(top_sku_count).index.astype(str))
    merged = merged[merged["product_id"].astype(str).isin(keep)]

    lines: list[RawOrderLine] = []
    for row in merged.itertuples(index=False):
        category = getattr(row, "product_category_name", None)
        if category is None or pd.isna(category):
            category = "unknown"
        score = getattr(row, "review_score", None)
        review_score = None if score is None or pd.isna(score) else int(score)
        lines.append(
            RawOrderLine(
                order_id=str(row.order_id),
                sku_id=str(row.product_id),
                seller_id=str(row.seller_id),
                purchased_at=_ts(row.order_purchase_timestamp, tz),
                price=_money(row.price),
                freight_value=_money(row.freight_value),
                order_status=str(row.order_status),
                category=str(category),
                review_score=review_score,
            )
        )
    return lines
