from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.config.settings import Settings, default_policy
from domain.business.metrics import MetricState
from domain.business.snapshot import BusinessStateSnapshot
from domain.common import BusinessPolicyConfig
from domain.issue.models import Issue
from repositories.business import InMemoryBusinessRepository
from repositories.issue import InMemoryIssueRepository
from repositories.snapshot import InMemorySnapshotRepository
from services.anomaly.engine import detect_issues
from services.ingestion.olist_loader import load_olist
from services.ingestion.snapshot_builder import build_snapshot
from services.ingestion.synthetic_ops import apply_synthetic
from services.metrics.aggregate import build_campaign_metric_states, build_sku_metric_states


class DailyRunResult:
    def __init__(
        self,
        snapshot: BusinessStateSnapshot,
        metrics: list[MetricState],
        issues: list[Issue],
    ) -> None:
        self.snapshot = snapshot
        self.metrics = metrics
        self.issues = issues


def run_daily(
    data_dir: Path,
    settings: Settings | None = None,
    policy: BusinessPolicyConfig | None = None,
    *,
    business_repo: InMemoryBusinessRepository | None = None,
    snapshot_repo: InMemorySnapshotRepository | None = None,
    issue_repo: InMemoryIssueRepository | None = None,
    now: datetime | None = None,
) -> DailyRunResult:
    settings = settings or Settings()
    policy = policy or default_policy()
    business_repo = business_repo or InMemoryBusinessRepository()
    snapshot_repo = snapshot_repo or InMemorySnapshotRepository()
    issue_repo = issue_repo or InMemoryIssueRepository()
    tz = ZoneInfo(settings.timezone)
    now = now or datetime.now(tz)

    lines = load_olist(
        data_dir,
        tz,
        seller_id=settings.store_seller_id,
        top_sku_count=settings.top_sku_count,
    )
    if not lines:
        raise ValueError("no order lines loaded")

    as_of = settings.as_of_date or max(line.purchased_at.date() for line in lines)
    freshness = max(line.purchased_at for line in lines)
    ops = apply_synthetic(
        lines,
        policy,
        tz,
        store_id=settings.store_id,
        store_name=settings.store_name,
        as_of=as_of,
    )
    business_repo.save_sku_daily(ops.sku_daily)
    business_repo.save_campaign_daily(ops.campaign_daily)
    version = snapshot_repo.current_version() + 1
    snapshot = build_snapshot(
        ops,
        as_of=as_of,
        snapshot_id=f"SNAP_{settings.store_id}_{as_of.isoformat()}_{version}",
        version=version,
        created_at=now,
        data_freshness_at=freshness,
    )
    snapshot_repo.save(snapshot)

    metrics: list[MetricState] = []
    for sku in snapshot.skus.values():
        metrics.extend(build_sku_metric_states(sku, ops.sku_daily, ops.campaign_daily, as_of, now))
    for campaign in snapshot.campaigns.values():
        metrics.extend(build_campaign_metric_states(campaign, ops.campaign_daily, as_of, now))

    issues, evidence = detect_issues(snapshot, metrics, policy, now)
    for item in evidence:
        issue_repo.save_evidence(item)
    for issue in issues:
        issue_repo.save_issue(issue)
    return DailyRunResult(snapshot=snapshot, metrics=metrics, issues=issues)
