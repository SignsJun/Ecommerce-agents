from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import Settings
from repositories.decision import FileDecisionRepository
from repositories.run import FileRunRepository
from services.runs.ingest import extract_olist_zip
from services.runs.pipeline import execute_run, new_run_id, pending_manifest
from services.runs.views import decision_payload, issue_payload, run_payload, trace_payload


def _truthy(value: object, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes"}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    run_repo = FileRunRepository(settings.runs_dir)
    decision_repo = FileDecisionRepository(settings.decisions_dir)
    app = FastAPI(title="Ecommerce Decision Agent")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.settings = settings
    app.state.run_repo = run_repo
    app.state.decision_repo = decision_repo

    def _now() -> datetime:
        return datetime.now(ZoneInfo(settings.timezone))

    def _kick(
        run_id: str,
        data_dir: Path,
        fake_llm: bool,
        n: int,
        source: str,
    ) -> None:
        execute_run(
            settings=settings,
            run_repo=run_repo,
            decision_repo=decision_repo,
            run_id=run_id,
            data_dir=data_dir,
            fake_llm=fake_llm,
            n=n,
            source=source,
        )

    async def _parse_create(request: Request) -> tuple[str, bool, int, bytes | None]:
        ctype = request.headers.get("content-type", "")
        source = "bundled"
        fake_llm = True
        n = 2
        raw: bytes | None = None
        if "multipart/form-data" in ctype:
            form = await request.form()
            source = str(form.get("source") or "bundled")
            fake_llm = _truthy(form.get("fake_llm"), True)
            n = int(form.get("n") or 2)
            up = form.get("file")
            if hasattr(up, "read"):
                raw = await up.read()
        elif "application/json" in ctype:
            body = await request.json()
            source = str(body.get("source") or "bundled")
            fake_llm = _truthy(body.get("fake_llm"), True)
            n = int(body.get("n", 2))
        else:
            source = request.query_params.get("source", "bundled")
            fake_llm = _truthy(request.query_params.get("fake_llm"), True)
            n = int(request.query_params.get("n", "2"))
        return source, fake_llm, n, raw

    @app.get("/api/v1/runs")
    def list_runs():
        return [run_payload(run_repo, m) for m in run_repo.list_manifests()]

    @app.post("/api/v1/runs")
    async def create_run(request: Request):
        source, fake_llm, n, raw = await _parse_create(request)
        if n < 1 or n > 64:
            raise HTTPException(400, "n out of range")
        if source not in {"bundled", "upload"}:
            raise HTTPException(400, "source must be bundled or upload")
        run_id = new_run_id()
        if source == "upload":
            if not raw:
                raise HTTPException(400, "upload requires a zip file")
            dest = settings.uploads_dir / run_id
            dest.mkdir(parents=True, exist_ok=True)
            zip_path = dest / f"{uuid4().hex[:8]}.zip"
            zip_path.write_bytes(raw)
            data_dir = extract_olist_zip(zip_path, dest)
        else:
            data_dir = Path(settings.data_dir)
            if not data_dir.exists():
                raise HTTPException(400, f"bundled data missing: {data_dir}")
        now = _now()
        manifest = pending_manifest(
            run_id=run_id,
            settings=settings,
            data_dir=data_dir,
            fake_llm=fake_llm,
            n=n,
            source=source,
            now=now,
        )
        run_repo.save_manifest(manifest)
        if fake_llm:
            _kick(run_id, data_dir, fake_llm, n, source)
        else:
            threading.Thread(
                target=_kick,
                args=(run_id, data_dir, fake_llm, n, source),
                daemon=True,
            ).start()
        stored = run_repo.get_manifest(run_id)
        if stored is None:
            raise HTTPException(500, "run not saved")
        return run_payload(run_repo, stored)

    @app.get("/api/v1/runs/{run_id}")
    def get_run(run_id: str):
        manifest = run_repo.get_manifest(run_id)
        if manifest is None:
            raise HTTPException(404, "run not found")
        return run_payload(run_repo, manifest)

    @app.get("/api/v1/runs/{run_id}/issues/{issue_id}")
    def get_issue(run_id: str, issue_id: str):
        manifest = run_repo.get_manifest(run_id)
        if manifest is None:
            raise HTTPException(404, "run not found")
        payload = issue_payload(run_repo, decision_repo, manifest, issue_id)
        if payload is None:
            raise HTTPException(404, "issue not found")
        return payload

    @app.get("/api/v1/runs/{run_id}/issues/{issue_id}/decision")
    def get_issue_decision(run_id: str, issue_id: str):
        manifest = run_repo.get_manifest(run_id)
        if manifest is None:
            raise HTTPException(404, "run not found")
        decision_id = manifest.issue_decisions.get(issue_id)
        if not decision_id:
            raise HTTPException(404, "decision not found")
        case = decision_repo.get(decision_id)
        if case is None:
            raise HTTPException(404, "decision not found")
        return decision_payload(case)

    @app.get("/api/v1/decisions/{decision_id}/trace")
    def get_trace(decision_id: str):
        case = decision_repo.get(decision_id)
        if case is None:
            raise HTTPException(404, "decision not found")
        return trace_payload(case)

    return app


app = create_app()
