from domain.issue.evidence import Evidence
from domain.issue.models import Issue


class InMemoryIssueRepository:
    def __init__(self) -> None:
        self._issues: dict[str, Issue] = {}
        self._evidence: dict[str, Evidence] = {}

    def save_issue(self, issue: Issue) -> None:
        self._issues[issue.issue_id] = issue

    def save_evidence(self, evidence: Evidence) -> None:
        self._evidence[evidence.evidence_id] = evidence

    def get_issue(self, issue_id: str) -> Issue | None:
        return self._issues.get(issue_id)

    def get_evidence(self, evidence_id: str) -> Evidence | None:
        return self._evidence.get(evidence_id)

    def list_open(self) -> list[Issue]:
        return [i for i in self._issues.values() if i.status == "open"]

    def list_by_snapshot(self, snapshot_id: str) -> list[Issue]:
        return [i for i in self._issues.values() if i.based_on_snapshot_id == snapshot_id]

    def list_evidence(self, evidence_ids: list[str]) -> list[Evidence]:
        return [self._evidence[eid] for eid in evidence_ids if eid in self._evidence]

    def list_all_evidence(self) -> list[Evidence]:
        return list(self._evidence.values())
