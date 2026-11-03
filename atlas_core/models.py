"""atlas_core.models — the domain-agnostic data model.

Atlas Core is a *semantic knowledge map* over "nodes": any unit of content
(a course, a lesson, an article, a DB table, a code function …). Only the
INGESTION decides what a node is; everything downstream (embed → cluster →
summarize → narrate → search) operates on these plain types, so the engine is
indifferent to whether the nodes came from code, courses, or support tickets.

Boring dataclasses on purpose. `kind` and `Link.type` are free-form strings
(NOT a fixed enum) — that is the single change that frees Atlas from being a
code-only tool.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(slots=True)
class Node:
    """One unit of content in the map.

    `text` is what gets embedded/summarized; `name` is a short human label;
    `kind` is a free-form type ("course", "lesson", "article", "faq", …);
    `source` is optional provenance (a URL, DB ref, or file path)."""
    id: str
    kind: str
    name: str
    text: str = ""
    attrs: dict[str, Any] = field(default_factory=dict)
    source: Optional[str] = None
    # Sub-scope WITHIN the store/tenant (e.g. an academy id in a multi-academy
    # platform). Index a node ONCE; query it at the group level (filter) or
    # globally (no filter) — no per-group re-embedding. None = ungrouped/global.
    group: Optional[str] = None
    embedding: Optional[list[float]] = None
    summary: Optional[str] = None
    topic_id: Optional[int] = None


@dataclass(slots=True)
class Link:
    """A directed relationship between two nodes. `type` is free-form
    ("lesson_in_module", "prereq_of", "references", "calls", …). For data (not
    code) these are best derived DETERMINISTICALLY from your own DB relations
    (foreign keys) rather than inferred — see docs/ingest."""
    src: str
    dst: str
    type: str
    weight: float = 1.0
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Topic:
    """A discovered cluster of nodes with an LLM/heuristic label. `group` records
    the scope it was computed for (an academy id, or None for a global topic)."""
    id: int
    label: str
    description: str = ""
    node_ids: list[str] = field(default_factory=list)
    group: Optional[str] = None


@dataclass(slots=True)
class Narrative:
    """A short prose description of a scope (the whole map, or a subset)."""
    scope: str
    text: str
    embedding: Optional[list[float]] = None
