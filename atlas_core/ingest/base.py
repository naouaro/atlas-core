"""atlas_core.ingest — turning a domain into nodes + links.

This is the ONLY domain-specific seam. Code extractors
(tree-sitter) are one kind of ingester; for an LMS or knowledge base you write a
content ingester that reads courses / lessons / articles (and derives links
DETERMINISTICALLY from your DB foreign keys). An ingester just yields
`Node`s and `Link`s — the engine does the rest.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Link, Node


class Ingester(ABC):
    @abstractmethod
    def nodes(self) -> list[Node]: ...

    def links(self) -> list[Link]:
        return []
