import argparse
from pathlib import Path

from app.config.settings import Settings
from services.daily_run import run_daily
from tools.diagnosis.investigate import context_from_run, investigate_issue


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run-daily")
    run.add_argument("--data-dir", type=Path, default=None)
    inv = sub.add_parser("investigate")
    inv.add_argument("--data-dir", type=Path, default=None)
    inv.add_argument("--issue-id", type=str, default=None)
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
    issue_id = args.issue_id or result.issues[0].issue_id
    ctx = context_from_run(result)
    outputs = investigate_issue(ctx, issue_id)
    print(f"investigate\tissue={issue_id}\ttools={len(outputs)}")
    for item in outputs:
        flag = "ok" if item.success else (item.error.error_code if item.error else "fail")
        print(f"{item.tool_name}\t{flag}\tevidence={len(item.evidence)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
