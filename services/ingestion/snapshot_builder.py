from datetime import date, datetime

from domain.business.snapshot import BusinessStateSnapshot
from domain.common import DataQualityReport
from services.ingestion.synthetic_ops import SyntheticOpsResult
from services.metrics.aggregate import build_campaign_state, build_sku_state


def build_snapshot(
    ops: SyntheticOpsResult,
    as_of: date,
    snapshot_id: str,
    version: int,
    created_at: datetime,
    data_freshness_at: datetime,
) -> BusinessStateSnapshot:
    skus = {}
    for sku_id, profile in ops.profiles.items():
        skus[sku_id] = build_sku_state(
            sku_id=sku_id,
            category=profile.category,
            price=profile.price,
            base_price=profile.base_price,
            unit_cost=profile.unit_cost,
            inventory_on_hand=profile.inventory_on_hand,
            inventory_available=profile.inventory_available,
            incoming_inventory=profile.incoming_inventory,
            lead_time_days=profile.lead_time_days,
            rows=ops.sku_daily,
            as_of=as_of,
            campaign_rows=ops.campaign_daily,
        )
    campaigns = {}
    campaign_ids = {row.campaign_id: row.sku_id for row in ops.campaign_daily}
    for campaign_id, sku_id in campaign_ids.items():
        campaigns[campaign_id] = build_campaign_state(
            campaign_id=campaign_id,
            sku_id=sku_id,
            rows=ops.campaign_daily,
            as_of=as_of,
        )
    completeness = 0.55 if ops.missing_sources else 1.0
    return BusinessStateSnapshot(
        snapshot_id=snapshot_id,
        version=version,
        created_at=created_at,
        data_freshness_at=data_freshness_at,
        store=ops.store,
        skus=skus,
        campaigns=campaigns,
        data_quality=DataQualityReport(
            completeness_score=completeness,
            freshness_score=1.0,
            consistency_score=1.0,
            missing_sources=ops.missing_sources,
            warnings=ops.warnings,
        ),
    )
