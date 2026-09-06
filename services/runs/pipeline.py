from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from agents.decision.agent import attach_simulations, plan
from agents.diagnosis.agent import diagnose
from agents.llm.factory import llm_from_settings
from agents.llm.scripts import scripted_llm, scripted_strategy_llm
from agents.simulation.agent import run_experiments
from app.config.settings import Settings
from domain.runs.manifest import RunManifest
from repositories.decision import FileDecisionRepository
from repositories.run import FileRunRepository
from services.artifact.archive import archive_decision
from services.daily_run import run_daily
from services.runs.kpi import compute_kpi
from tools.diagnosis.investigate import context_from_run


def new_run_id() -> str:
    return f"RUN_{uuid4().hex[:12]}"


def pending_manifest(
    *,
    run_id: str,
    settings: Settings,
    data_dir: Path,
    fake_llm: bool,
    n: int,
    source: str,
    now: datetime,
) -> RunManifest:
    return RunManifest(
        run_id=run_id,
        status="pending",
        source="upload" if source == "upload" else "bundled",
        fake_llm=fake_llm,
        llm="fake" if fake_llm else settings.llm_model,
        n=n,
        created_at=now,
        data_dir=str(data_dir),
        store_id=settings.store_id,
        store_name=settings.store_name,
    )


def execute_run(
    *,
    settings: Settings,
    run_repo: FileRunRepository,
    decision_repo: FileDecisionRepository,
    run_id: str,
    data_dir: Path,
    fake_llm: bool = True,
    n: int = 2,
    source: str = "bundled",
    now: datetime | None = None,
) -> RunManifest:
    tz = ZoneInfo(settings.timezone)
    now = now or datetime.now(tz)
    manifest = run_repo.get_manifest(run_id) or pending_manifest(
        run_id=run_id,
        settings=settings,
        data_dir=data_dir,
        fake_llm=fake_llm,
        n=n,
        source=source,
        now=now,
    )
    manifest = manifest.model_copy(update={"status": "running", "data_dir": str(data_dir)})
    run_repo.save_manifest(manifest)
    try:
        daily = run_daily(
            data_dir,
            settings=settings,
            now=now,
            snapshot_id=f"SNAP_{run_id}",
        )
        kpi = compute_kpi(daily.snapshot, daily.issues)
        run_repo.save_bundle(
            run_id,
            snapshot=daily.snapshot,
            issues=daily.issues,
            evidence=daily.issue_repo.list_all_evidence(),
            sku_daily=daily.business_repo.list_all_sku_daily(),
            campaign_daily=daily.business_repo.list_all_campaign_daily(),
        )
        mapping = dict(manifest.issue_decisions)
        decision_ids = list(manifest.decision_ids)
        manifest = manifest.model_copy(
            update={
                "as_of": daily.as_of,
                "snapshot_id": daily.snapshot.snapshot_id,
                "issue_ids": [i.issue_id for i in daily.issues],
                "kpi": kpi,
            }
        )
        run_repo.save_manifest(manifest)
        ctx = context_from_run(daily)
        live_llm = None if fake_llm else llm_from_settings(settings)
        for issue in daily.issues:
            diag_llm = scripted_llm(issue.issue_type) if fake_llm else live_llm
            strat_llm = scripted_strategy_llm(issue.issue_type) if fake_llm else live_llm
            outcome = diagnose(issue, ctx, diag_llm)
            planned = plan(issue, outcome.report, ctx, strat_llm)
            planned = attach_simulations(planned, ctx, n=n, llm=None if fake_llm else strat_llm)
            exp = run_experiments(planned, ctx, llm=None if fake_llm else strat_llm, n=n)
            stored = archive_decision(planned, ctx, decision_repo, experiment=exp)
            mapping[issue.issue_id] = stored.record.decision_id
            decision_ids.append(stored.record.decision_id)
            run_repo.save_bundle(run_id, evidence=daily.issue_repo.list_all_evidence())
            manifest = manifest.model_copy(
                update={"issue_decisions": dict(mapping), "decision_ids": list(decision_ids)}
            )
            run_repo.save_manifest(manifest)
        finished = datetime.now(tz)
        manifest = manifest.model_copy(update={"status": "done", "finished_at": finished})
        run_repo.save_manifest(manifest)
        return manifest
    except Exception as exc:
        failed = datetime.now(tz)
        manifest = manifest.model_copy(update={"status": "failed", "finished_at": failed, "error": str(exc)})
        run_repo.save_manifest(manifest)
        return manifest
