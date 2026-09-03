import argparse
from pathlib import Path

from app.config.settings import Settings
from services.daily_run import run_daily


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run-daily")
    run.add_argument("--data-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.cmd != "run-daily":
        parser.error("unknown command")
    settings = Settings()
    data_dir = args.data_dir or settings.data_dir
    result = run_daily(data_dir, settings=settings)
    print(f"snapshot={result.snapshot.snapshot_id} skus={len(result.snapshot.skus)} issues={len(result.issues)}")
    for issue in result.issues:
        print(
            f"{issue.issue_type.value}\t{issue.entity_id}\t{issue.severity}\t"
            f"impact={issue.estimated_impact}\tevidence={len(issue.evidence_ids)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
