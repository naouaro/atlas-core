"""atlas_core.engine.pipeline — the Atlas facade.

Ties the generic core together: ingest → embed → cluster → summarize →
narrate → search. Pluggable embedder / store / llm; everything degrades to an
offline path when no cloud model is configured.

    from atlas_core import Atlas
    from atlas_core.providers.local import LocalEmbeddingProvider
    atlas = Atlas(embedder=LocalEmbeddingProvider())
    atlas.ingest(nodes, links)
    atlas.build()                      # embed + cluster + summarize + narrate
    atlas.search("الشهادات")           # semantic search (multilingual)
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..models import Link, Narrative, Node, Topic
from ..providers.base import EmbeddingProvider, LLMProvider
from ..store.base import VectorStore
from ..store.memory import InMemoryVectorStore
from ..textnorm import tokens as _tokens
from . import cluster as _cluster
from . import summarize as _sum

if TYPE_CHECKING:
    from .glossary import Glossary


class Atlas:
    def __init__(self, embedder: EmbeddingProvider,
                 store: VectorStore | None = None,
                 llm: LLMProvider | None = None) -> None:
        self.embedder = embedder
        self.store = store or InMemoryVectorStore()
        self.llm = llm
        self.narrative: Narrative | None = None

    # ── ingest ────────────────────────────────────────────────────────────
    def ingest(self, nodes: list[Node], links: list[Link] | None = None) -> None:
        self.store.upsert_nodes(nodes)
        if links:
            self.store.upsert_links(links)

    def sync(self, nodes: list[Node], links: list[Link] | None = None,
             prune_group: str | None = None, batch: int = 128) -> dict:
        """Incrementally update the map. Re-embeds ONLY nodes whose content changed
        (by hash) or that are new; carries over the stored vector for unchanged
        content (no wasted embedding). Idempotent (upsert by id).

        `prune_group`: if set, delete nodes in that group that are NOT in `nodes`
        (content deleted upstream). Pass the FULL current set for that group.
        Watermarking (pull only rows changed since last run) belongs in the
        ingester's SQL (WHERE updateAt > :last) — this handles embed-reuse + prune.
        """
        import hashlib  # noqa: PLC0415
        existing = {n.id: n for n in self.store.all_nodes()}
        to_embed: list[Node] = []
        for n in nodes:
            h = hashlib.sha256(f"{n.name}\n{n.text}".encode("utf-8")).hexdigest()
            n.attrs["_hash"] = h
            prev = existing.get(n.id)
            if prev is not None and prev.attrs.get("_hash") == h and prev.embedding is not None:
                n.embedding = prev.embedding          # unchanged → reuse, skip embed
            else:
                to_embed.append(n)
        for i in range(0, len(to_embed), batch):
            chunk = to_embed[i:i + batch]
            vecs = self.embedder.embed([f"{n.name}\n{n.text}".strip() for n in chunk])
            for n, v in zip(chunk, vecs):
                n.embedding = v
        self.store.upsert_nodes(nodes)
        if links:
            self.store.upsert_links(links)
        pruned = 0
        if prune_group is not None:
            incoming = {n.id for n in nodes}
            stale = [n.id for n in self.store.all_nodes(group=prune_group)
                     if n.id not in incoming]
            pruned = self.store.delete_nodes(stale)
        return {"total": len(nodes), "reembedded": len(to_embed),
                "reused": len(nodes) - len(to_embed), "pruned": pruned}

    def embed_all(self, batch: int = 128) -> int:
        todo = [n for n in self.store.all_nodes() if n.embedding is None]
        for i in range(0, len(todo), batch):
            chunk = todo[i:i + batch]
            vecs = self.embedder.embed([f"{n.name}\n{n.text}".strip() for n in chunk])
            for n, v in zip(chunk, vecs):
                n.embedding = v
        self.store.upsert_nodes(todo)
        return len(todo)

    # ── enrich (per-group or global) ──────────────────────────────────────
    def cluster(self, k: int | None = None, group: str | None = None) -> list[Topic]:
        nodes = self.store.all_nodes(group=group)
        topics = _cluster.cluster_nodes(nodes, llm=self.llm, k=k, group=group)
        self.store.upsert_topics(topics)
        self.store.upsert_nodes(nodes)  # persist topic_id
        return topics

    def summarize(self) -> None:
        nodes = self.store.all_nodes()
        _sum.summarize_nodes(nodes, llm=self.llm)
        self.store.upsert_nodes(nodes)

    def narrate(self, group: str | None = None) -> Narrative:
        topics = [t for t in self.store.all_topics() if t.group == group]
        nodes = self.store.all_nodes(group=group)
        narr = _sum.narrate(topics, nodes, llm=self.llm, scope=group or "map")
        if group is None:
            self.narrative = narr
        return narr

    def groups(self) -> list[str]:
        """Distinct non-null groups present (e.g. every academy indexed)."""
        return sorted({n.group for n in self.store.all_nodes() if n.group})

    def build(self, do_summaries: bool = True) -> "Atlas":
        """One-shot GLOBAL build: embed everything, discover global topics,
        (summaries), narrate. Call cluster(group=X)/narrate(group=X) per academy."""
        self.embed_all()
        if do_summaries:
            self.summarize()
        self.cluster()
        self.narrate()
        return self

    # ── query ─────────────────────────────────────────────────────────────
    def search(self, query: str, k: int = 10, kind: str | None = None,
               group: str | None = None, expand: "Glossary | None" = None,
               hybrid: bool = False, alpha: float = 0.6) -> list[tuple[Node, float]]:
        """Semantic search.

        `expand` (a Glossary) enriches the query with domain vocabulary before
        embedding. `hybrid=True` reranks the vector candidates by blending cosine with
        lexical token-overlap — ``alpha``·vector + ``(1-alpha)``·lexical — which is
        language-agnostic (Arabic/Turkish/Latin) and helps when exact terms matter.
        """
        if expand is not None:
            query = expand.expand_query(query)
        qv = self.embedder.embed([query])[0]
        if not hybrid:
            return self.store.search(qv, k=k, kind=kind, group=group)
        # oversample on the vector side, then blend in a lexical overlap score.
        cand = self.store.search(qv, k=max(k * 5, 20), kind=kind, group=group)
        qtok = set(_tokens(query, min_len=2))
        if not qtok:
            return cand[:k]
        rescored = []
        for node, vsim in cand:
            dtok = set(_tokens(f"{node.name} {node.text}", min_len=2))
            lex = len(qtok & dtok) / len(qtok)
            rescored.append((node, alpha * vsim + (1.0 - alpha) * lex))
        rescored.sort(key=lambda nx: -nx[1])
        return rescored[:k]

    def related(self, node_id: str) -> list[Link]:
        return self.store.links_for(node_id)

    def topics(self, group: str | None = None) -> list[Topic]:
        return [t for t in self.store.all_topics() if t.group == group]
