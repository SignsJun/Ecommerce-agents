from services.artifact.provenance import explain
from tests.unit.test_artifact_render import make_case


def test_recommended_traces_to_evidence():
    case = make_case()
    relations = {(e.source_id, e.relation, e.target_id) for e in case.provenance.edges}
    assert ("SNAP_184", "detected", "ISSUE_018") in relations
    assert ("E101", "supports", "D18") in relations
    assert ("D18", "proposes", "STRAT_B") in relations
    assert ("SIM_27", "informs", "REC_STRAT_B") in relations
    assert ("REC_STRAT_B", "selects", "STRAT_B") in relations
    text = explain(case, "STRAT_B")
    assert "E101" in text
    assert "ad_efficiency" in text
    assert "rank=1" in text
    assert "sim\tbase" in text


def test_rejected_has_reject_edge():
    case = make_case()
    assert any(e.relation == "rejects" and e.target_id == "ST_mid" for e in case.provenance.edges)
    text = explain(case, "ST_mid")
    assert "reject" in text
    assert "rejected_after_eval" in text
