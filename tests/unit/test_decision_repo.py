from domain.enums import IssueType
from repositories.decision import FileDecisionRepository
from tests.unit.test_artifact_render import make_case


def test_save_get_roundtrip(tmp_path):
    repo = FileDecisionRepository(tmp_path)
    case = make_case()
    artifacts = repo.save(case)
    assert len(artifacts) == 6
    assert all(a.content_hash for a in artifacts)
    folder = tmp_path / "DEC_018"
    for name in (
        "01_issue_brief.md",
        "02_diagnosis_report.md",
        "03_strategy_proposals.md",
        "04_simulation_report.md",
        "05_decision_record.md",
        "case.json",
        "provenance.json",
    ):
        assert (folder / name).exists()
    loaded = repo.get("DEC_018")
    assert loaded is not None
    assert loaded.record.decision_id == "DEC_018"
    assert loaded.recommendations[0].strategy_id == "STRAT_B"
    assert loaded.diagnosis.root_causes[0].cause_type == "ad_efficiency"
    assert loaded.evidence[0].evidence_id == "E101"
    assert len(loaded.provenance.edges) == len(case.provenance.edges)


def test_list_by_issue_type(tmp_path):
    repo = FileDecisionRepository(tmp_path)
    repo.save(make_case())
    rows = repo.list_by_issue_type(IssueType.PROFIT_EROSION)
    assert [r.decision_id for r in rows] == ["DEC_018"]
    assert repo.list_by_issue_type(IssueType.STOCKOUT_RISK) == []
    assert repo.get("missing") is None
