from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal
from uuid import uuid4
from zoneinfo import ZoneInfo

from domain.base import FrozenModel
from domain.common import BusinessPolicyConfig, TimeRange
from domain.diagnosis.hypothesis import ToolCallRecord
from domain.enums import DataProvenance
from domain.issue.evidence import Evidence
from repositories.business import InMemoryBusinessRepository
from repositories.issue import InMemoryIssueRepository
from repositories.snapshot import InMemorySnapshotRepository
from tools.diagnosis.payloads import ToolPayload

TOOL_VERSION = "v1"

ErrorCode = Literal["not_found", "empty_result", "unavailable"]


class ToolError(FrozenModel):
    error_code: ErrorCode
    message: str
    tool_name: str


class ToolResult(FrozenModel):
    tool_name: str
    tool_version: str
    success: bool
    error: ToolError | None = None
    produces_evidence: bool
    evidence: list[Evidence]
    payload: ToolPayload | None = None
    call: ToolCallRecord


@dataclass
class ToolContext:
    snapshot_id: str
    snapshot_repo: InMemorySnapshotRepository
    issue_repo: InMemoryIssueRepository
    business_repo: InMemoryBusinessRepository
    policy: BusinessPolicyConfig
    as_of: date
    tz: ZoneInfo
    now: datetime

    def snapshot(self):
        return self.snapshot_repo.get(self.snapshot_id)

    def bounds(self, start: date, end: date) -> tuple[datetime, datetime]:
        return (
            datetime(start.year, start.month, start.day, tzinfo=self.tz),
            datetime(end.year, end.month, end.day, 23, 59, 59, tzinfo=self.tz),
        )

    def period(self, start: date, end: date) -> TimeRange:
        lo, hi = self.bounds(start, end)
        return TimeRange(start=lo, end=hi)


def fail(
    ctx: ToolContext,
    tool_name: str,
    error_code: ErrorCode,
    message: str,
    arguments: dict[str, str | int | float | bool | None],
) -> ToolResult:
    return ToolResult(
        tool_name=tool_name,
        tool_version=TOOL_VERSION,
        success=False,
        error=ToolError(error_code=error_code, message=message, tool_name=tool_name),
        produces_evidence=True,
        evidence=[],
        payload=None,
        call=ToolCallRecord(
            tool_name=tool_name,
            tool_version=TOOL_VERSION,
            arguments=arguments,
            success=False,
            error_code=error_code,
            evidence_ids=[],
            called_at=ctx.now,
        ),
    )


def make_evidence(
    ctx: ToolContext,
    tool_name: str,
    *,
    entity_type: str,
    entity_id: str,
    metric: str,
    value: str | int | float | bool | None,
    description: str,
    comparison: str | None = None,
    period: TimeRange | None = None,
    reliability: float = 0.85,
    provenance: DataProvenance = DataProvenance.DERIVED,
) -> Evidence:
    return Evidence(
        evidence_id=f"EV_{tool_name}_{uuid4().hex[:12]}",
        source_type="diagnosis_tool",
        source_ref=tool_name,
        entity_type=entity_type,
        entity_id=entity_id,
        metric=metric,
        value=value,
        comparison=comparison,
        period=period,
        description=description,
        reliability=reliability,
        provenance=provenance,
        tool_name=tool_name,
        tool_version=TOOL_VERSION,
        snapshot_id=ctx.snapshot_id,
        created_at=ctx.now,
    )


def ok(
    ctx: ToolContext,
    tool_name: str,
    payload: ToolPayload,
    evidence: list[Evidence],
    arguments: dict[str, str | int | float | bool | None],
    *,
    produces_evidence: bool = True,
) -> ToolResult:
    if produces_evidence:
        for item in evidence:
            ctx.issue_repo.save_evidence(item)
    return ToolResult(
        tool_name=tool_name,
        tool_version=TOOL_VERSION,
        success=True,
        error=None,
        produces_evidence=produces_evidence,
        evidence=evidence if produces_evidence else [],
        payload=payload,
        call=ToolCallRecord(
            tool_name=tool_name,
            tool_version=TOOL_VERSION,
            arguments=arguments,
            success=True,
            error_code=None,
            evidence_ids=[e.evidence_id for e in evidence] if produces_evidence else [],
            called_at=ctx.now,
        ),
    )
