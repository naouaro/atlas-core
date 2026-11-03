"""atlas_core.store.memory — in-memory numpy store (zero infra).

Good for demos, tests, and maps up to ~100k nodes. Cosine via a single
normalized matrix multiply. Swap in PgVectorStore for production/persistence.
"""
from __future__ import annotations

import numpy as np

from ..models import Link, Node, Topic
from .base import VectorStore


class InMemoryVectorStore(VectorStore):
    def __init__(self) -> None:
        self._nodes: dict[str, Node] = {}
        self._links: list[Link] = []
        self._topics: dict[tuple, Topic] = {}   # keyed by (group, id)

    def upsert_nodes(self, nodes: list[Node]) -> None:
        for n in nodes:
            self._nodes[n.id] = n

    def get_node(self, node_id: str) -> Node | None:
        return self._nodes.get(node_id)

    def all_nodes(self, kind: str | None = None,
                  group: str | None = None) -> list[Node]:
        return [n for n in self._nodes.values()
                if (kind is None or n.kind == kind)
                and (group is None or n.group == group)]

    def search(self, vector: list[float], k: int = 10, kind: str | None = None,
               group: str | None = None) -> list[tuple[Node, float]]:
        pool = [n for n in self._nodes.values()
                if n.embedding is not None
                and (kind is None or n.kind == kind)
                and (group is None or n.group == group)]
        if not pool:
            return []
        mat = np.asarray([n.embedding for n in pool], dtype=np.float32)
        q = np.asarray(vector, dtype=np.float32)
        # normalize (providers should already, but be safe)
        mat /= (np.linalg.norm(mat, axis=1, keepdims=True) + 1e-9)
        q /= (np.linalg.norm(q) + 1e-9)
        sims = mat @ q
        order = np.argsort(-sims)[:k]
        return [(pool[i], float(sims[i])) for i in order]

    def delete_nodes(self, ids: list[str]) -> int:
        n = 0
        for i in ids:
            if self._nodes.pop(i, None) is not None:
                n += 1
        return n

    def upsert_links(self, links: list[Link]) -> None:
        self._links.extend(links)

    def links_for(self, node_id: str) -> list[Link]:
        return [l for l in self._links if l.src == node_id or l.dst == node_id]

    def upsert_topics(self, topics: list[Topic]) -> None:
        for t in topics:
            self._topics[(t.group, t.id)] = t   # topics are per-group

    def all_topics(self) -> list[Topic]:
        return list(self._topics.values())
