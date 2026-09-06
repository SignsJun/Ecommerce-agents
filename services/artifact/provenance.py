from __future__ import annotations

from domain.decision.case import DecisionCase
from domain.decision.provenance import NodeType, ProvenanceEdge, ProvenanceGraph, ProvenanceNode
from domain.decision.recommendation import StrategyRecommendation
from domain.diagnosis.report import DiagnosisReport
from domain.issue.evidence import Evidence
from domain.issue.models import Issue
from domain.simulation.report import SimulationReport
from domain.strategy.models import Strategy
from domain.strategy.validation import StrategyValidationResult


def _scene(report: SimulationReport) -> str:
    if report.scenario_results:
        return report.scenario_results[0].scenario_id
    return "base"


def _node(nodes: dict[str, ProvenanceNode], node_id: str, node_type: NodeType, label: str) -> None:
    if node_id not in nodes:
        nodes[node_id] = ProvenanceNode(node_id=node_id, node_type=node_type, label=label)


def _rec_id(sid: str) -> str:
    return f"REC_{sid}"


def _val_id(sid: str) -> str:
    return f"VAL_{sid}"


def build_graph(
    *,
    decision_id: str,
    snapshot_id: str,
    issue: Issue,
    evidence: list[Evidence],
    diagnosis: DiagnosisReport | None,
    strategies: list[Strategy],
    validations: list[StrategyValidationResult],
    simulations: list[SimulationReport],
    recommendations: list[StrategyRecommendation],
    rejected_after_eval: list[str],
    rejected_strategy_ids: list[str],
) -> ProvenanceGraph:
    nodes: dict[str, ProvenanceNode] = {}
    edges: list[ProvenanceEdge] = []
    _node(nodes, snapshot_id, "snapshot", snapshot_id)
    _node(nodes, issue.issue_id, "issue", issue.issue_type.value)
    _node(nodes, decision_id, "decision", decision_id)
    edges.append(ProvenanceEdge(source_id=snapshot_id, target_id=issue.issue_id, relation="detected"))
    by_eid = {e.evidence_id: e for e in evidence}
    for eid in issue.evidence_ids:
        item = by_eid.get(eid)
        _node(nodes, eid, "evidence", item.metric or eid if item else eid)
        edges.append(ProvenanceEdge(source_id=issue.issue_id, target_id=eid, relation="has"))
    diag_id = diagnosis.diagnosis_id if diagnosis else None
    if diagnosis is not None:
        _node(nodes, diagnosis.diagnosis_id, "diagnosis", diagnosis.status)
        support_ids = list(diagnosis.key_evidence_ids)
        for cause in diagnosis.root_causes:
            support_ids.extend(cause.supporting_evidence_ids)
        seen: set[str] = set()
        for eid in support_ids:
            if eid in seen:
                continue
            seen.add(eid)
            item = by_eid.get(eid)
            _node(nodes, eid, "evidence", item.metric or eid if item else eid)
            edges.append(ProvenanceEdge(source_id=eid, target_id=diagnosis.diagnosis_id, relation="supports"))
    strat_ids = {s.strategy_id for s in strategies}
    for sid in [*rejected_strategy_ids, *rejected_after_eval]:
        strat_ids.add(sid)
    by_sid = {s.strategy_id: s for s in strategies}
    for sid in strat_ids:
        item = by_sid.get(sid)
        label = item.strategy_type if item else sid
        _node(nodes, sid, "strategy", label)
        if diag_id is not None:
            edges.append(ProvenanceEdge(source_id=diag_id, target_id=sid, relation="proposes"))
    for row in validations:
        vid = _val_id(row.strategy_id)
        _node(nodes, vid, "validation", "feasible" if row.feasible else "infeasible")
        _node(nodes, row.strategy_id, "strategy", by_sid[row.strategy_id].strategy_type if row.strategy_id in by_sid else row.strategy_id)
        edges.append(ProvenanceEdge(source_id=row.strategy_id, target_id=vid, relation="validated_as"))
    rec_ids = {r.strategy_id for r in recommendations}
    for row in simulations:
        _node(nodes, row.simulation_id, "simulation", _scene(row))
        _node(nodes, row.strategy_id, "strategy", by_sid[row.strategy_id].strategy_type if row.strategy_id in by_sid else row.strategy_id)
        edges.append(ProvenanceEdge(source_id=row.strategy_id, target_id=row.simulation_id, relation="evaluated_by"))
        if row.strategy_id in rec_ids:
            rid = _rec_id(row.strategy_id)
            edges.append(ProvenanceEdge(source_id=row.simulation_id, target_id=rid, relation="informs"))
    for rec in recommendations:
        rid = _rec_id(rec.strategy_id)
        _node(nodes, rid, "recommendation", f"rank{rec.rank}:{rec.recommendation_type}")
        _node(nodes, rec.strategy_id, "strategy", by_sid[rec.strategy_id].strategy_type if rec.strategy_id in by_sid else rec.strategy_id)
        edges.append(ProvenanceEdge(source_id=rid, target_id=rec.strategy_id, relation="selects"))
    rejected = list(dict.fromkeys([*rejected_strategy_ids, *rejected_after_eval]))
    for sid in rejected:
        _node(nodes, sid, "strategy", by_sid[sid].strategy_type if sid in by_sid else sid)
        edges.append(ProvenanceEdge(source_id=decision_id, target_id=sid, relation="rejects"))
    return ProvenanceGraph(decision_id=decision_id, nodes=list(nodes.values()), edges=edges)


def explain(case: DecisionCase, strategy_id: str) -> str:
    rec = next((r for r in case.recommendations if r.strategy_id == strategy_id), None)
    rejected = strategy_id in case.record.rejected_after_eval or strategy_id in case.record.rejected_strategy_ids
    lines = [f"explain\tstrategy={strategy_id}\tdecision={case.record.decision_id}"]
    if rec is not None:
        lines.append(
            f"  rec\trank={rec.rank}\ttype={rec.recommendation_type}\tconfidence={rec.confidence}\t"
            f"profit={rec.expected_profit}\tvs_base={rec.vs_baseline}"
        )
        lines.append(
            f"  labels\tstrengths={','.join(rec.strengths) or '-'}\trisks={','.join(rec.risks) or '-'}\t"
            f"suitable={','.join(rec.suitable_when) or '-'}\tsupport={','.join(rec.simulation_support) or '-'}"
        )
    if rejected:
        why = []
        if strategy_id in case.record.rejected_after_eval:
            why.append("rejected_after_eval")
        if strategy_id in case.record.rejected_strategy_ids:
            why.append("rejected_strategy")
        lines.append(f"  reject\t{','.join(why)}")
    if case.diagnosis is not None:
        causes = ",".join(c.cause_type for c in case.diagnosis.root_causes) or "-"
        lines.append(f"  causes\t{causes}\tstatus={case.diagnosis.status}")
    by_eid = {e.evidence_id: e for e in case.evidence}
    eids: list[str] = []
    if case.diagnosis is not None:
        eids.extend(case.diagnosis.key_evidence_ids)
        for cause in case.diagnosis.root_causes:
            eids.extend(cause.supporting_evidence_ids)
    eids.extend(case.issue.evidence_ids)
    seen: set[str] = set()
    for eid in eids:
        if eid in seen:
            continue
        seen.add(eid)
        item = by_eid.get(eid)
        desc = item.description if item else "-"
        metric = item.metric if item else "-"
        lines.append(f"  evidence\t{eid}\t{metric}\t{desc}")
    for row in case.simulations:
        if row.strategy_id != strategy_id:
            continue
        lines.append(
            f"  sim\t{_scene(row)}\tprofit={row.expected_profit}\tp10={row.profit_p10}\t"
            f"vs_base={row.expected_profit - row.baseline_profit}"
        )
    return "\n".join(lines)
