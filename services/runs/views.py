from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from domain.business.inventory import days_of_cover
from domain.business.sku import SKUDailyMetric, SKUState
from domain.decision.case import DecisionCase
from domain.issue.evidence import Evidence
from domain.issue.models import Issue
from domain.runs.manifest import RunManifest
from repositories.decision import FileDecisionRepository
from repositories.run import FileRunRepository
from services.artifact.provenance import explain
from services.runs.kpi import kpi_delta


def dump(model) -> dict | None:
    if model is None:
        return None
    return model.model_dump(mode="json")


def previous_done(repo: FileRunRepository, current: RunManifest) -> RunManifest | None:
    older = [
        m
        for m in repo.list_manifests()
        if m.status == "done" and m.run_id != current.run_id and m.created_at < current.created_at and m.kpi is not None
    ]
    if not older:
        return None
    return max(older, key=lambda m: m.created_at)


def store_series(rows: list[SKUDailyMetric]) -> list[dict]:
    buckets: dict[str, dict] = {}
    for row in rows:
        key = row.metric_date.date().isoformat()
        item = buckets.setdefault(key, {"date": key, "revenue": 0.0, "profit": 0.0, "ad_spend": 0.0})
        item["revenue"] += float(row.revenue)
        item["profit"] += float(row.profit)
        item["ad_spend"] += float(row.ad_spend)
    return sorted(buckets.values(), key=lambda x: x["date"])


def _window(rows: list[SKUDailyMetric], as_of: date, end_ago: int, days: int) -> dict[str, Decimal]:
    end = as_of - timedelta(days=end_ago)
    start = end - timedelta(days=days - 1)
    acc = {
        "revenue": Decimal("0"),
        "profit": Decimal("0"),
        "ad_spend": Decimal("0"),
        "refund_loss": Decimal("0"),
        "units_sold": Decimal("0"),
    }
    for row in rows:
        day = row.metric_date.date()
        if start <= day <= end:
            acc["revenue"] += row.revenue
            acc["profit"] += row.profit
            acc["ad_spend"] += row.ad_spend
            acc["refund_loss"] += row.refund_loss
            acc["units_sold"] += Decimal(row.units_sold)
    return acc


def sku_drivers(sku: SKUState, rows: list[SKUDailyMetric], as_of: date) -> list[dict]:
    mine = [r for r in rows if r.sku_id == sku.sku_id]
    cur = _window(mine, as_of, 0, 7)
    prev = _window(mine, as_of, 7, 7)

    def row(name: str, current: float, previous: float | None) -> dict:
        delta = None
        if previous not in (None, 0):
            delta = (current - previous) / abs(previous)
        return {"name": name, "current": current, "previous": previous, "delta": delta}

    cover = days_of_cover(sku.inventory_available, sku.units_sold_7d)
    return [
        row("revenue", float(cur["revenue"]), float(prev["revenue"])),
        row("profit", float(cur["profit"]), float(prev["profit"])),
        row("ad_spend", float(cur["ad_spend"]), float(prev["ad_spend"])),
        row("refund_loss", float(cur["refund_loss"]), float(prev["refund_loss"])),
        row("units_sold", float(cur["units_sold"]), float(prev["units_sold"])),
        row("refund_rate_7d", float(sku.refund_rate_7d), None),
        row("roas_7d", float(sku.roas_7d) if sku.roas_7d is not None else 0.0, sku.roas_prev_7d),
        row("days_of_cover", cover, None),
    ]


def sku_trend(sku_id: str, rows: list[SKUDailyMetric]) -> list[dict]:
    out = []
    for row in sorted((r for r in rows if r.sku_id == sku_id), key=lambda r: r.metric_date):
        out.append(
            {
                "date": row.metric_date.date().isoformat(),
                "revenue": float(row.revenue),
                "profit": float(row.profit),
                "ad_spend": float(row.ad_spend),
                "units_sold": row.units_sold,
                "inventory_eod": row.inventory_eod,
            }
        )
    return out


def issue_row(issue: Issue, decision_id: str | None) -> dict:
    body = dump(issue) or {}
    body["decision_id"] = decision_id
    body["title"] = f"{issue.issue_type.value} · {issue.entity_id}"
    return body


def run_payload(repo: FileRunRepository, manifest: RunManifest) -> dict:
    prev = previous_done(repo, manifest)
    issues = repo.get_issues(manifest.run_id)
    mapping = manifest.issue_decisions
    delta = kpi_delta(manifest.kpi, prev.kpi) if manifest.kpi and prev and prev.kpi else None
    return {
        **(dump(manifest) or {}),
        "kpi_delta": delta,
        "previous_run_id": prev.run_id if prev else None,
        "issues": [issue_row(i, mapping.get(i.issue_id)) for i in issues],
        "series": store_series(repo.get_sku_daily(manifest.run_id)),
    }


def _issue_evidence(issue: Issue, evidence: list[Evidence], case: DecisionCase | None) -> list[dict]:
    wanted: list[str] = list(issue.evidence_ids)
    if case and case.diagnosis is not None:
        wanted.extend(case.diagnosis.key_evidence_ids)
        for cause in case.diagnosis.root_causes:
            wanted.extend(cause.supporting_evidence_ids)
    by_id = {e.evidence_id: e for e in evidence}
    if case:
        for item in case.evidence:
            by_id[item.evidence_id] = item
    seen: set[str] = set()
    out: list[dict] = []
    for eid in wanted:
        if eid in seen:
            continue
        seen.add(eid)
        item = by_id.get(eid)
        if item is not None:
            out.append(dump(item) or {})
    return out


def issue_payload(
    repo: FileRunRepository,
    decisions: FileDecisionRepository,
    manifest: RunManifest,
    issue_id: str,
) -> dict | None:
    issues = repo.get_issues(manifest.run_id)
    issue = next((i for i in issues if i.issue_id == issue_id), None)
    if issue is None:
        return None
    snapshot = repo.get_snapshot(manifest.run_id)
    sku_daily = repo.get_sku_daily(manifest.run_id)
    campaign_daily = repo.get_campaign_daily(manifest.run_id)
    sku = snapshot.skus.get(issue.entity_id) if snapshot else None
    decision_id = manifest.issue_decisions.get(issue_id)
    case = decisions.get(decision_id) if decision_id else None
    as_of = manifest.as_of or date.today()
    return {
        "run_id": manifest.run_id,
        "decision_id": decision_id,
        "issue": issue_row(issue, decision_id),
        "sku": dump(sku),
        "drivers": sku_drivers(sku, sku_daily, as_of) if sku else [],
        "trend": sku_trend(issue.entity_id, sku_daily),
        "campaign_trend": [
            {
                "date": r.metric_date.date().isoformat(),
                "campaign_id": r.campaign_id,
                "spend": float(r.spend),
                "attributed_revenue": float(r.attributed_revenue),
                "clicks": r.clicks,
                "conversions": r.conversions,
            }
            for r in sorted(
                (c for c in campaign_daily if c.sku_id == issue.entity_id),
                key=lambda c: c.metric_date,
            )
        ],
        "diagnosis": dump(case.diagnosis) if case else None,
        "evidence": _issue_evidence(issue, repo.get_evidence(manifest.run_id), case),
    }


def decision_payload(case: DecisionCase) -> dict:
    rec_by = {r.strategy_id: r for r in case.recommendations}
    rejected = set(case.record.rejected_after_eval) | set(case.record.rejected_strategy_ids)
    rec_ids = set(rec_by)
    candidates = []
    for strat in case.strategies:
        rec = rec_by.get(strat.strategy_id)
        sims = [dump(s) for s in case.simulations if s.strategy_id == strat.strategy_id]
        candidates.append(
            {
                "strategy": dump(strat),
                "recommended": strat.strategy_id in rec_ids,
                "rejected": strat.strategy_id in rejected,
                "recommendation": dump(rec),
                "simulations": sims,
            }
        )
    return {
        "decision_id": case.record.decision_id,
        "issue_id": case.issue.issue_id,
        "issue_type": case.issue.issue_type.value,
        "experiment_status": case.record.experiment_status,
        "recommendations": [dump(r) for r in case.recommendations],
        "rejected_after_eval": list(case.record.rejected_after_eval),
        "rejected_strategy_ids": list(case.record.rejected_strategy_ids),
        "candidates": candidates,
    }


def trace_payload(case: DecisionCase) -> dict:
    rec_ids = [r.strategy_id for r in case.recommendations]
    stages = ["snapshot", "issue", "evidence", "diagnosis", "strategy", "simulation", "recommendation", "decision"]
    grouped: dict[str, list[dict]] = {s: [] for s in stages}
    for node in case.provenance.nodes:
        grouped.setdefault(node.node_type, []).append(dump(node) or {})
    return {
        "decision_id": case.record.decision_id,
        "issue_id": case.issue.issue_id,
        "graph": dump(case.provenance),
        "stages": [{"stage": s, "nodes": grouped.get(s, [])} for s in stages if grouped.get(s)],
        "explains": {sid: explain(case, sid) for sid in rec_ids},
    }
