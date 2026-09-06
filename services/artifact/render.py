from __future__ import annotations

from agents.simulation.compare import scenario_of
from domain.decision.case import DecisionCase
from domain.strategy.models import Strategy


def _yaml(fields: dict[str, object]) -> str:
    lines = ["---"]
    for key, value in fields.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            if not value:
                lines.append("  []")
            else:
                for item in value:
                    lines.append(f"  - {item}")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines)


def _action(strategy: Strategy) -> str:
    if not strategy.actions:
        return "do_nothing"
    parts = []
    for action in strategy.actions:
        extra = getattr(action, "change_pct", None)
        if extra is None:
            extra = getattr(action, "quantity", None)
        if extra is None:
            extra = getattr(action, "target_issue", None)
        target = getattr(action, "campaign_id", None) or getattr(action, "sku_id", None) or "-"
        parts.append(f"{action.action_type}:{target}:{extra}")
    return ",".join(parts)


def render_documents(case: DecisionCase) -> dict[str, str]:
    rec = case.record
    issue = case.issue
    diag = case.diagnosis
    generated = rec.created_at.isoformat()
    snapshot_id = rec.snapshot_id
    evidence_ids = [e.evidence_id for e in case.evidence] or list(issue.evidence_ids)
    base = {
        "decision_id": rec.decision_id,
        "issue_id": issue.issue_id,
        "business_snapshot": snapshot_id,
        "generated_at": generated,
        "evidence": evidence_ids,
        "status": "final",
    }
    by_sid = {s.strategy_id: s for s in case.strategies}
    by_val = {v.strategy_id: v for v in case.validations}
    rec_ids = {r.strategy_id for r in case.recommendations}

    issue_body = [
        _yaml({**base, "document_type": "issue_brief", "agent": "archive-v1"}),
        "",
        "# Issue Brief",
        "",
        f"- type: {issue.issue_type.value}",
        f"- entity: {issue.entity_type}/{issue.entity_id}",
        f"- severity: {issue.severity}",
        f"- confidence: {issue.confidence}",
        f"- impact: {issue.estimated_impact}",
        f"- snapshot: {issue.based_on_snapshot_id}",
        f"- evidence: {', '.join(issue.evidence_ids) or '-'}",
    ]

    diag_lines = [
        _yaml(
            {
                **base,
                "document_type": "diagnosis_report",
                "agent": "diagnosis-agent",
                "agent_version": diag.agent_version if diag else "-",
                "model": diag.model_version if diag else "-",
            }
        ),
        "",
        "# Diagnosis Report",
        "",
    ]
    if diag is None:
        diag_lines.append("status: none")
    else:
        diag_lines.append(f"- status: {diag.status}")
        diag_lines.append(f"- coverage: {diag.active_investigation_coverage}")
        diag_lines.append(f"- confidence: {diag.overall_confidence}")
        diag_lines.append("- root_causes:")
        if not diag.root_causes:
            diag_lines.append("  - none")
        for cause in diag.root_causes:
            eids = ",".join(cause.supporting_evidence_ids) or "-"
            diag_lines.append(f"  - {cause.cause_type}\tconf={cause.confidence}\tevidence={eids}")
        diag_lines.append(f"- uncertainties: {', '.join(diag.uncertainties) or '-'}")

    strat_lines = [
        _yaml({**base, "document_type": "strategy_proposals", "agent": "archive-v1"}),
        "",
        "# Strategy Proposals",
        "",
    ]
    for strategy in case.strategies:
        val = by_val.get(strategy.strategy_id)
        feasible = val.feasible if val else False
        reason = val.errors[0].code if val and val.errors else "-"
        strat_lines.append(
            f"- {strategy.strategy_id}\t{strategy.strategy_type}\tfeasible={feasible}\t"
            f"reject={reason if not feasible else '-'}\t{_action(strategy)}"
        )
    extra = [sid for sid in rec.rejected_strategy_ids if sid not in by_sid]
    for sid in extra:
        val = by_val.get(sid)
        reason = val.errors[0].code if val and val.errors else "-"
        strat_lines.append(f"- {sid}\t-\tfeasible=False\treject={reason}")

    sim_lines = [
        _yaml({**base, "document_type": "simulation_report", "agent": "archive-v1"}),
        "",
        "# Simulation Report",
        "",
        f"- experiment_status: {rec.experiment_status or '-'}",
        "",
    ]
    if not case.simulations:
        sim_lines.append("none")
    for row in case.simulations:
        scene = scenario_of(row)
        sim_lines.append(
            f"- {row.strategy_id}\t{scene}\tprofit={row.expected_profit}\tp10={row.profit_p10}\t"
            f"vs_base={row.expected_profit - row.baseline_profit}\tstockout={row.stockout_probability:.2f}"
        )

    rec_lines = [
        _yaml({**base, "document_type": "decision_record", "agent": "archive-v1"}),
        "",
        "# Decision Record",
        "",
        f"问题：{issue.issue_type.value} ({issue.entity_id})",
        "",
        "根因：",
    ]
    if diag is None or not diag.root_causes:
        rec_lines.append("- none")
    else:
        for cause in diag.root_causes:
            rec_lines.append(f"- {cause.cause_type} conf={cause.confidence}")
    rec_lines.append("")
    rec_lines.append("候选方案：")
    for strategy in case.strategies:
        rec_lines.append(f"- {strategy.strategy_id} {strategy.strategy_type} {_action(strategy)}")
    scenes = sorted({scenario_of(r) for r in case.simulations}) or ["base"]
    rec_lines.append("")
    rec_lines.append("模拟：")
    for scene in scenes:
        rec_lines.append(f"- {scene}")
    rec_lines.append("")
    rec_lines.append("最终建议：")
    if not case.recommendations:
        rec_lines.append("- none")
    for item in case.recommendations:
        rec_lines.append(
            f"{item.rank}. {item.recommendation_type} {item.strategy_id} "
            f"profit={item.expected_profit} vs_base={item.vs_baseline} "
            f"support={','.join(item.simulation_support) or '-'}"
        )
        rec_lines.append(f"   strengths={','.join(item.strengths) or '-'}")
        rec_lines.append(f"   risks={','.join(item.risks) or '-'}")
        rec_lines.append(f"   suitable={','.join(item.suitable_when) or '-'}")
    rec_lines.append("")
    rec_lines.append("不推荐：")
    rejected = list(dict.fromkeys([*rec.rejected_after_eval, *rec.rejected_strategy_ids]))
    shown = False
    for sid in rejected:
        if sid in rec_ids:
            continue
        shown = True
        why = "rejected_after_eval" if sid in rec.rejected_after_eval else "rejected_strategy"
        rec_lines.append(f"- {sid} 原因：{why}")
    if not shown:
        rec_lines.append("- none")

    return {
        "01_issue_brief.md": "\n".join(issue_body) + "\n",
        "02_diagnosis_report.md": "\n".join(diag_lines) + "\n",
        "03_strategy_proposals.md": "\n".join(strat_lines) + "\n",
        "04_simulation_report.md": "\n".join(sim_lines) + "\n",
        "05_decision_record.md": "\n".join(rec_lines) + "\n",
    }
