import argparse
from pathlib import Path

from agents.diagnosis.agent import diagnose
from agents.llm.client import LLMUnavailable
from agents.llm.factory import llm_from_settings
from agents.llm.scripts import scripted_llm
from app.config.settings import Settings
from domain.enums import IssueType
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
    args = parser.parse_args(argv)
    settings = Settings()
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
        llm = scripted_llm(issue.issue_type)
    else:
        try:
            llm = llm_from_settings(settings)
        except LLMUnavailable as exc:
            print(str(exc))
            return 1
    outcome = diagnose(issue, ctx, llm)
    report = outcome.report
    print(
        f"diagnose\tissue={issue.issue_id}\tstatus={report.status}\t"
        f"tools={len(outcome.state.tool_history)}\tirrelevant={outcome.irrelevant_tool_requests}\t"
        f"model={report.model_version}"
    )
    for cause in report.root_causes:
        print(
            f"cause\t{cause.cause_type}\tconf={cause.confidence}\t"
            f"evidence={len(cause.supporting_evidence_ids)}"
        )
    print(f"uncertainties\t{len(report.uncertainties)}\tkey_evidence={len(report.key_evidence_ids)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
