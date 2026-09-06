from __future__ import annotations

import hashlib
from pathlib import Path

from domain.decision.case import DecisionCase
from domain.decision.record import DecisionRecord
from domain.decision.state import DecisionArtifact
from domain.enums import IssueType

AGENT = "archive-v1"


class FileDecisionRepository:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def _dir(self, decision_id: str) -> Path:
        return self.root / decision_id

    def case_dir(self, decision_id: str) -> Path:
        return self._dir(decision_id)

    def save(self, case: DecisionCase) -> list[DecisionArtifact]:
        from services.artifact.render import render_documents
        folder = self._dir(case.record.decision_id)
        folder.mkdir(parents=True, exist_ok=True)
        docs = render_documents(case)
        extras = {
            "provenance.json": case.provenance.model_dump_json(indent=2) + "\n",
        }
        artifacts: list[DecisionArtifact] = []
        files = [
            ("01_issue_brief.md", "issue_brief", docs["01_issue_brief.md"]),
            ("02_diagnosis_report.md", "diagnosis_report", docs["02_diagnosis_report.md"]),
            ("03_strategy_proposals.md", "strategy_proposals", docs["03_strategy_proposals.md"]),
            ("04_simulation_report.md", "simulation_report", docs["04_simulation_report.md"]),
            ("05_decision_record.md", "decision_record", docs["05_decision_record.md"]),
            ("provenance.json", "provenance", extras["provenance.json"]),
        ]
        evidence_ids = [e.evidence_id for e in case.evidence]
        snapshot_ids = [case.snapshot.snapshot_id]
        for name, atype, body in files:
            path = folder / name
            encoded = body.encode("utf-8")
            path.write_bytes(encoded)
            digest = hashlib.sha256(encoded).hexdigest()
            artifacts.append(
                DecisionArtifact(
                    artifact_id=f"ART_{digest[:12]}",
                    artifact_type=atype,
                    decision_id=case.record.decision_id,
                    issue_id=case.issue.issue_id,
                    version=1,
                    status="final",
                    created_at=case.record.created_at,
                    created_by=AGENT,
                    model_version=case.diagnosis.model_version if case.diagnosis else None,
                    source_snapshot_ids=snapshot_ids,
                    evidence_ids=evidence_ids,
                    related_artifact_ids=[],
                    document_uri=str(path),
                    content_hash=digest,
                )
            )
        related = [a.artifact_id for a in artifacts]
        artifacts = [a.model_copy(update={"related_artifact_ids": [i for i in related if i != a.artifact_id]}) for a in artifacts]
        filled = case.model_copy(update={"artifacts": artifacts})
        (folder / "case.json").write_text(filled.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return artifacts

    def get(self, decision_id: str) -> DecisionCase | None:
        path = self._dir(decision_id) / "case.json"
        if not path.exists():
            return None
        return DecisionCase.model_validate_json(path.read_text(encoding="utf-8"))

    def document(self, decision_id: str, name: str) -> str | None:
        path = self._dir(decision_id) / name
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def list_by_issue_type(self, issue_type: IssueType | str | None = None) -> list[DecisionRecord]:
        if not self.root.exists():
            return []
        wanted = None if issue_type is None else IssueType(issue_type) if not isinstance(issue_type, IssueType) else issue_type
        rows: list[DecisionRecord] = []
        for path in sorted(self.root.glob("*/case.json")):
            case = DecisionCase.model_validate_json(path.read_text(encoding="utf-8"))
            if wanted is not None and case.record.issue_type != wanted:
                continue
            rows.append(case.record)
        return rows
