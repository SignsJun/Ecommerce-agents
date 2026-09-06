import argparse
from pathlib import Path

from agents.decision.agent import attach_simulations, format_plan_trace, format_simulation_trace, plan, plan_from_rules
from agents.diagnosis.agent import diagnose, format_diagnosis_trace
from agents.llm.client import LLMUnavailable
from agents.llm.factory import llm_from_settings
from agents.llm.scripts import scripted_llm, scripted_strategy_llm
from agents.simulation.agent import format_experiment_trace, run_experiments
from app.config.settings import Settings
from domain.enums import IssueType
from repositories.decision import FileDecisionRepository
from services.artifact.archive import archive_decision
from services.artifact.provenance import explain
from services.daily_run import run_daily
from tools.diagnosis.investigate import context_from_run, investigate_issue


def _pick_issue(issues, issue_id: str | None):
    if issue_id:
        for item in issues:
            if item.issue_id == issue_id:
                return item
        return None
    for item in issues:
        if item.issue_type == IssueType.PROFIT_EROSION:
            return item
    return issues[0]


def _repo(args, settings: Settings) -> FileDecisionRepository:
    root = getattr(args, "decisions_dir", None) or settings.decisions_dir
    return FileDecisionRepository(root)


def _memory_cmd(args, settings: Settings) -> int:
    repo = _repo(args, settings)
    if args.cmd == "cases":
        rows = repo.list_by_issue_type(getattr(args, "issue_type", None))
        print(f"cases\tn={len(rows)}")
        for rec in rows:
            print(
                f"case\t{rec.decision_id}\tissue_type={rec.issue_type.value}\t"
                f"issue={rec.issue_id}\tn_recs={len(rec.recommendations)}"
            )
        return 0
    case = repo.get(args.decision_id)
    if case is None:
        print(f"case\tnot_found\t{args.decision_id}")
        return 1
    if args.cmd == "case":
        body = repo.document(args.decision_id, "05_decision_record.md")
        print(body or "")
        return 0
    print(f"trace\tdecision={case.record.decision_id}\tnodes={len(case.provenance.nodes)}\tedges={len(case.provenance.edges)}")
    sid = getattr(args, "strategy_id", None)
    if sid:
        print(explain(case, sid))
        return 0
    for node in case.provenance.nodes:
        print(f"node\t{node.node_type}\t{node.node_id}\t{node.label}")
    for edge in case.provenance.edges:
        print(f"edge\t{edge.source_id}\t{edge.relation}\t{edge.target_id}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run-daily")
    run.add_argument("--data-dir", type=Path, default=None)
    inv = sub.add_parser("investigate")
    inv.add_argument("--data-dir", type=Path, default=None)
    inv.add_argument("--issue-id", type=str, default=None)
    diag = sub.add_parser("diagnose")
    diag.add_argument("--data-dir", type=Path, default=None)
    diag.add_argument("--issue-id", type=str, default=None)
    diag.add_argument("--fake-llm", action="store_true")
    pln = sub.add_parser("plan")
    pln.add_argument("--data-dir", type=Path, default=None)
    pln.add_argument("--issue-id", type=str, default=None)
    pln.add_argument("--fake-llm", action="store_true")
    pln.add_argument("--rule-baseline", action="store_true")
    sim = sub.add_parser("simulate")
    sim.add_argument("--data-dir", type=Path, default=None)
    sim.add_argument("--issue-id", type=str, default=None)
    sim.add_argument("--fake-llm", action="store_true")
    sim.add_argument("--rule-baseline", action="store_true")
    sim.add_argument("--open-loop", action="store_true")
    sim.add_argument("--experiment", action="store_true")
    arc = sub.add_parser("archive")
    arc.add_argument("--data-dir", type=Path, default=None)
    arc.add_argument("--issue-id", type=str, default=None)
    arc.add_argument("--fake-llm", action="store_true")
    arc.add_argument("--rule-baseline", action="store_true")
    arc.add_argument("--open-loop", action="store_true")
    arc.add_argument("--n", type=int, default=32)
    arc.add_argument("--decisions-dir", type=Path, default=None)
    cases = sub.add_parser("cases")
    cases.add_argument("--issue-type", type=str, default=None)
    cases.add_argument("--decisions-dir", type=Path, default=None)
    case_p = sub.add_parser("case")
    case_p.add_argument("decision_id")
    case_p.add_argument("--decisions-dir", type=Path, default=None)
    tr = sub.add_parser("trace")
    tr.add_argument("decision_id")
    tr.add_argument("--strategy-id", type=str, default=None)
    tr.add_argument("--decisions-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    settings = Settings()
    if args.cmd in {"cases", "case", "trace"}:
        return _memory_cmd(args, settings)
    data_dir = args.data_dir or settings.data_dir
    result = run_daily(data_dir, settings=settings)
    print(f"snapshot={result.snapshot.snapshot_id} skus={len(result.snapshot.skus)} issues={len(result.issues)}")
    for issue in result.issues:
        print(
            f"{issue.issue_type.value}\t{issue.entity_id}\t{issue.severity}\t"
            f"impact={issue.estimated_impact}\tevidence={len(issue.evidence_ids)}"
        )
    if args.cmd == "run-daily":
        return 0
    if not result.issues:
        return 1
    ctx = context_from_run(result)
    if args.cmd == "investigate":
        issue_id = args.issue_id or result.issues[0].issue_id
        outputs = investigate_issue(ctx, issue_id)
        print(f"investigate\tissue={issue_id}\ttools={len(outputs)}")
        for item in outputs:
            flag = "ok" if item.success else (item.error.error_code if item.error else "fail")
            print(f"{item.tool_name}\t{flag}\tevidence={len(item.evidence)}")
        return 0
    issue = _pick_issue(result.issues, args.issue_id)
    if issue is None:
        print("issue not found")
        return 1
    if args.fake_llm:
        diag_llm = scripted_llm(issue.issue_type)
        strat_llm = scripted_strategy_llm(issue.issue_type)
    else:
        try:
            diag_llm = llm_from_settings(settings)
        except LLMUnavailable as exc:
            print(str(exc))
            return 1
        strat_llm = diag_llm
    outcome = diagnose(issue, ctx, diag_llm)
    report = outcome.report
    print(
        f"diagnose\tissue={issue.issue_id}\tstatus={report.status}\t"
        f"tools={report.tool_calls_used}\tirrelevant={outcome.irrelevant_tool_requests}\t"
        f"coverage={report.active_investigation_coverage}\tmodel={report.model_version}"
    )
    if args.cmd == "diagnose":
        print(format_diagnosis_trace(outcome))
        return 0
    if args.rule_baseline:
        planned = plan_from_rules(issue, report, ctx)
    else:
        planned = plan(issue, report, ctx, strat_llm)
    print(format_plan_trace(planned))
    if args.cmd == "plan":
        return 0
    n = getattr(args, "n", 32)
    planned = attach_simulations(
        planned,
        ctx,
        n=n,
        open_loop=getattr(args, "open_loop", False),
        llm=None if args.fake_llm else strat_llm,
    )
    print(format_simulation_trace(planned))
    if args.cmd == "simulate" and not getattr(args, "experiment", False):
        return 0
    exp = None
    if args.cmd == "archive" or getattr(args, "experiment", False):
        exp = run_experiments(
            planned,
            ctx,
            llm=None if args.fake_llm else strat_llm,
            n=n,
            open_loop=getattr(args, "open_loop", False),
        )
        print(format_experiment_trace(exp))
    if args.cmd != "archive":
        return 0
    repo = _repo(args, settings)
    stored = archive_decision(planned, ctx, repo, experiment=exp)
    print(f"decision={stored.record.decision_id}\tdir={repo.case_dir(stored.record.decision_id)}\tartifacts={len(stored.artifacts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
