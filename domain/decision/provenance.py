from typing import Literal

from domain.base import FrozenModel

NodeType = Literal[
    "snapshot",
    "issue",
    "evidence",
    "diagnosis",
    "strategy",
    "validation",
    "simulation",
    "recommendation",
    "decision",
]


class ProvenanceNode(FrozenModel):
    node_id: str
    node_type: NodeType
    label: str


class ProvenanceEdge(FrozenModel):
    source_id: str
    target_id: str
    relation: str


class ProvenanceGraph(FrozenModel):
    decision_id: str
    nodes: list[ProvenanceNode] = []
    edges: list[ProvenanceEdge] = []
