from datetime import datetime

from domain.base import FrozenModel
from domain.business.campaign import CampaignState
from domain.business.sku import SKUState
from domain.common import DataQualityReport, StoreState


class BusinessStateSnapshot(FrozenModel):
    snapshot_id: str
    version: int
    created_at: datetime
    data_freshness_at: datetime
    store: StoreState
    skus: dict[str, SKUState]
    campaigns: dict[str, CampaignState]
    data_quality: DataQualityReport
