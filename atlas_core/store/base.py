"""atlas_core.store.base — pluggable storage for nodes, links, topics.

Two backends ship: an in-memory store (numpy cosine; zero infra, for demos /
tests / small maps) and a Postgres+pgvector store (the production backend).
The engine only uses this interface.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Link, Node, Topic


class VectorStore(ABC):
    @abstractmethod
    def upsert_nodes(self, nodes: list[Node]) -> None: ...

    @abstractmethod
    def get_node(self, node_id: str) -> Node | None: ...

    @abstractmethod
    def all_nodes(self, kind: str | None = None,
                  group: str | None = None) -> list[Node]: ...

    @abstractmethod
    def search(self, vector: list[float], k: int = 10, kind: str | None = None,
               group: str | None = None) -> list[tuple[Node, float]]:
        """Return up to k (node, cosine_similarity) pairs, best first. `group`
        scopes the search to one sub-tenant (e.g. an academy); None = across all."""

    @abstractmethod
    def delete_nodes(self, ids: list[str]) -> int:
        """Remove nodes by id (for pruning content deleted upstream)."""

    @abstractmethod
    def upsert_links(self, links: list[Link]) -> None: ...

    @abstractmethod
    def links_for(self, node_id: str) -> list[Link]: ...

    @abstractmethod
    def upsert_topics(self, topics: list[Topic]) -> None: ...

    @abstractmethod
    def all_topics(self) -> list[Topic]: ...
