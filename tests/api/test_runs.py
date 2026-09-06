from zipfile import ZipFile

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.config.settings import Settings
from domain.enums import IssueType
from tests.fixtures.make_olist import AS_OF, write_mini_olist


def _client(tmp_path, data_dir=None):
    data_dir = data_dir or write_mini_olist(tmp_path / "olist")
    settings = Settings(
        as_of_date=AS_OF,
        store_seller_id="seller_demo",
        timezone="UTC",
        data_dir=data_dir,
        runs_dir=tmp_path / "runs",
        decisions_dir=tmp_path / "decisions",
        uploads_dir=tmp_path / "uploads",
    )
    return TestClient(create_app(settings)), data_dir


def test_fake_llm_run_four_pages(tmp_path):
    client, _ = _client(tmp_path)
    created = client.post("/api/v1/runs", json={"source": "bundled", "fake_llm": True, "n": 2})
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["status"] == "done"
    assert body["kpi"]["gmv"]
    assert body["snapshot_id"].startswith("SNAP_")
    run_id = body["run_id"]
    types = {i["issue_type"] for i in body["issues"]}
    assert types == {t.value for t in IssueType}
    assert all(i["decision_id"] for i in body["issues"])
    listed = client.get("/api/v1/runs")
    assert listed.status_code == 200
    assert any(r["run_id"] == run_id for r in listed.json())
    overview = client.get(f"/api/v1/runs/{run_id}")
    assert overview.status_code == 200
    assert overview.json()["series"]
    for issue in body["issues"]:
        issue_id = issue["issue_id"]
        detail = client.get(f"/api/v1/runs/{run_id}/issues/{issue_id}")
        assert detail.status_code == 200, detail.text
        payload = detail.json()
        assert payload["diagnosis"]
        assert payload["drivers"]
        assert payload["trend"]
        assert payload["evidence"]
        decision = client.get(f"/api/v1/runs/{run_id}/issues/{issue_id}/decision")
        assert decision.status_code == 200, decision.text
        d = decision.json()
        recs = d["recommendations"]
        assert 1 <= len(recs) <= 3
        rec_ids = {r["strategy_id"] for r in recs}
        cand_ids = {c["strategy"]["strategy_id"] for c in d["candidates"]}
        assert rec_ids <= cand_ids
        for c in d["candidates"]:
            sid = c["strategy"]["strategy_id"]
            assert c["recommended"] == (sid in rec_ids)
            if c["recommended"]:
                assert c["recommendation"]["strategy_id"] == sid
                assert c["recommendation"]["rank"] >= 1
        trace = client.get(f"/api/v1/decisions/{issue['decision_id']}/trace")
        assert trace.status_code == 200, trace.text
        graph = trace.json()["graph"]
        assert graph["nodes"]
        assert graph["edges"]
        assert trace.json()["explains"]


def test_upload_zip_run(tmp_path):
    data_dir = write_mini_olist(tmp_path / "olist")
    zpath = tmp_path / "olist.zip"
    with ZipFile(zpath, "w") as zf:
        for path in data_dir.glob("*.csv"):
            zf.write(path, path.name)
    client, _ = _client(tmp_path, data_dir=tmp_path / "unused")
    resp = client.post(
        "/api/v1/runs",
        data={"source": "upload", "fake_llm": "true", "n": "2"},
        files={"file": ("olist.zip", zpath.read_bytes(), "application/zip")},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "done"
    types = {i["issue_type"] for i in resp.json()["issues"]}
    assert types == {t.value for t in IssueType}
    assert all(i["decision_id"] for i in resp.json()["issues"])


def test_run_not_found(tmp_path):
    client, _ = _client(tmp_path)
    assert client.get("/api/v1/runs/RUN_missing").status_code == 404
