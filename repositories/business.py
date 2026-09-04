from datetime import datetime

from domain.business.campaign import CampaignDailyMetric
from domain.business.review import ReviewRecord
from domain.business.sku import SKUDailyMetric


class InMemoryBusinessRepository:
    def __init__(self) -> None:
        self._sku_daily: list[SKUDailyMetric] = []
        self._campaign_daily: list[CampaignDailyMetric] = []
        self._reviews: list[ReviewRecord] = []

    def save_sku_daily(self, rows: list[SKUDailyMetric]) -> None:
        self._sku_daily.extend(rows)

    def save_campaign_daily(self, rows: list[CampaignDailyMetric]) -> None:
        self._campaign_daily.extend(rows)

    def list_sku_daily(self, sku_id: str, start: datetime, end: datetime) -> list[SKUDailyMetric]:
        return [
            r
            for r in self._sku_daily
            if r.sku_id == sku_id and start <= r.metric_date <= end
        ]

    def list_campaign_daily(
        self, campaign_id: str, start: datetime, end: datetime
    ) -> list[CampaignDailyMetric]:
        return [
            r
            for r in self._campaign_daily
            if r.campaign_id == campaign_id and start <= r.metric_date <= end
        ]

    def list_all_sku_daily(self) -> list[SKUDailyMetric]:
        return list(self._sku_daily)

    def list_all_campaign_daily(self) -> list[CampaignDailyMetric]:
        return list(self._campaign_daily)

    def list_campaigns_for_sku(self, sku_id: str) -> list[str]:
        seen: list[str] = []
        found: set[str] = set()
        for row in self._campaign_daily:
            if row.sku_id == sku_id and row.campaign_id not in found:
                found.add(row.campaign_id)
                seen.append(row.campaign_id)
        return seen

    def save_reviews(self, rows: list[ReviewRecord]) -> None:
        self._reviews.extend(rows)

    def list_reviews(self, sku_id: str, start: datetime, end: datetime) -> list[ReviewRecord]:
        return [
            r
            for r in self._reviews
            if r.sku_id == sku_id and start <= r.reviewed_at <= end
        ]
