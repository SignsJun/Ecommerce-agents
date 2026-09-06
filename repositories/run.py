from __future__ import annotations

from pathlib import Path

from pydantic import TypeAdapter

from domain.business.campaign import CampaignDailyMetric
from domain.business.sku import SKUDailyMetric
from domain.business.snapshot import BusinessStateSnapshot
from domain.issue.evidence import Evidence
from domain.issue.models import Issue
from domain.runs.manifest import RunManifest

_ISSUES = TypeAdapter(list[Issue])
_EVIDENCE = TypeAdapter(list[Evidence])
_SKU_DAILY = TypeAdapter(list[SKUDailyMetric])
_CAMPAIGN_DAILY = TypeAdapter(list[CampaignDailyMetric])


class FileRunRepository:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def _dir(self, run_id: str) -> Path:
        return self.root / run_id

    def save_manifest(self, manifest: RunManifest) -> None:
        folder = self._dir(manifest.run_id)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "manifest.json").write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")

    def get_manifest(self, run_id: str) -> RunManifest | None:
        path = self._dir(run_id) / "manifest.json"
        if not path.exists():
            return None
        return RunManifest.model_validate_json(path.read_text(encoding="utf-8"))

    def list_manifests(self) -> list[RunManifest]:
        if not self.root.exists():
            return []
        rows: list[RunManifest] = []
        for path in self.root.glob("*/manifest.json"):
            rows.append(RunManifest.model_validate_json(path.read_text(encoding="utf-8")))
        rows.sort(key=lambda m: m.created_at, reverse=True)
        return rows

    def save_bundle(
        self,
        run_id: str,
        *,
        snapshot: BusinessStateSnapshot | None = None,
        issues: list[Issue] | None = None,
        evidence: list[Evidence] | None = None,
        sku_daily: list[SKUDailyMetric] | None = None,
        campaign_daily: list[CampaignDailyMetric] | None = None,
    ) -> None:
        folder = self._dir(run_id)
        folder.mkdir(parents=True, exist_ok=True)
        if snapshot is not None:
            (folder / "snapshot.json").write_text(snapshot.model_dump_json(indent=2) + "\n", encoding="utf-8")
        if issues is not None:
            (folder / "issues.json").write_bytes(_ISSUES.dump_json(issues, indent=2) + b"\n")
        if evidence is not None:
            (folder / "evidence.json").write_bytes(_EVIDENCE.dump_json(evidence, indent=2) + b"\n")
        if sku_daily is not None:
            (folder / "sku_daily.json").write_bytes(_SKU_DAILY.dump_json(sku_daily, indent=2) + b"\n")
        if campaign_daily is not None:
            (folder / "campaign_daily.json").write_bytes(_CAMPAIGN_DAILY.dump_json(campaign_daily, indent=2) + b"\n")

    def get_snapshot(self, run_id: str) -> BusinessStateSnapshot | None:
        path = self._dir(run_id) / "snapshot.json"
        if not path.exists():
            return None
        return BusinessStateSnapshot.model_validate_json(path.read_text(encoding="utf-8"))

    def get_issues(self, run_id: str) -> list[Issue]:
        path = self._dir(run_id) / "issues.json"
        if not path.exists():
            return []
        return _ISSUES.validate_json(path.read_text(encoding="utf-8"))

    def get_evidence(self, run_id: str) -> list[Evidence]:
        path = self._dir(run_id) / "evidence.json"
        if not path.exists():
            return []
        return _EVIDENCE.validate_json(path.read_text(encoding="utf-8"))

    def get_sku_daily(self, run_id: str) -> list[SKUDailyMetric]:
        path = self._dir(run_id) / "sku_daily.json"
        if not path.exists():
            return []
        return _SKU_DAILY.validate_json(path.read_text(encoding="utf-8"))

    def get_campaign_daily(self, run_id: str) -> list[CampaignDailyMetric]:
        path = self._dir(run_id) / "campaign_daily.json"
        if not path.exists():
            return []
        return _CAMPAIGN_DAILY.validate_json(path.read_text(encoding="utf-8"))
