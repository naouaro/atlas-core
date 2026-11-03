"""atlas_core.store.postgres — Postgres + pgvector backend (production).

`pip install atlas-core[postgres]` (psycopg + pgvector). Persistent; cosine *search*
scales to large corpora via pgvector (clustering/narration load vectors in memory, so
size that step for your RAM — mini-batch k-means keeps it bounded). Per-tenant isolation:
pass `tenant` and it is stored + filtered on every query (a lightweight stand-in
for row-level security — enable real RLS in your own deployment if needed).

Schema is created on first use (CREATE TABLE IF NOT EXISTS). Embedding dim is
fixed at construction and must match your provider.
"""
from __future__ import annotations

import json

from ..models import Link, Node, Topic
from .base import VectorStore


class PgVectorStore(VectorStore):
    def __init__(self, dsn: str, dim: int, tenant: str = "default",
                 table_prefix: str = "atlas"):
        import psycopg  # noqa: PLC0415
        from pgvector.psycopg import register_vector  # noqa: PLC0415
        self._conn = psycopg.connect(dsn, autocommit=True)
        self._conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        register_vector(self._conn)
        self.dim = dim
        self.tenant = tenant
        self.N = f"{table_prefix}_nodes"
        self.L = f"{table_prefix}_links"
        self.T = f"{table_prefix}_topics"
        self._conn.execute(
            f"CREATE TABLE IF NOT EXISTS {self.N} (tenant text, id text, kind text, "
            f"name text, text text, attrs jsonb, source text, summary text, "
            f"topic_id int, node_group text, embedding vector({dim}), "
            f"PRIMARY KEY (tenant, id))")
        self._conn.execute(
            f"CREATE INDEX IF NOT EXISTS {self.N}_group ON {self.N} (tenant, node_group)")
        self._conn.execute(
            f"CREATE TABLE IF NOT EXISTS {self.L} (tenant text, src text, dst text, "
            f"type text, weight float, attrs jsonb)")
        self._conn.execute(
            f"CREATE TABLE IF NOT EXISTS {self.T} (tenant text, id int, label text, "
            f"description text, node_ids jsonb, PRIMARY KEY (tenant, id))")

    def upsert_nodes(self, nodes: list[Node]) -> None:
        with self._conn.cursor() as cur:
            for n in nodes:
                cur.execute(
                    f"INSERT INTO {self.N} (tenant,id,kind,name,text,attrs,source,"
                    f"summary,topic_id,node_group,embedding) "
                    f"VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                    f"ON CONFLICT (tenant,id) DO UPDATE SET kind=EXCLUDED.kind,"
                    f"name=EXCLUDED.name,text=EXCLUDED.text,attrs=EXCLUDED.attrs,"
                    f"source=EXCLUDED.source,summary=EXCLUDED.summary,"
                    f"topic_id=EXCLUDED.topic_id,node_group=EXCLUDED.node_group,"
                    f"embedding=EXCLUDED.embedding",
                    (self.tenant, n.id, n.kind, n.name, n.text, json.dumps(n.attrs),
                     n.source, n.summary, n.topic_id, n.group, n.embedding))

    def _row(self, r) -> Node:
        emb = r[9]
        if emb is not None and not isinstance(emb, list):
            if hasattr(emb, "to_list"):      # pgvector.Vector
                emb = emb.to_list()
            elif hasattr(emb, "tolist"):     # numpy
                emb = emb.tolist()
            else:
                emb = list(emb)
        return Node(id=r[0], kind=r[1], name=r[2], text=r[3] or "",
                    attrs=r[4] or {}, source=r[5], summary=r[6], topic_id=r[7],
                    group=r[8], embedding=emb)

    _COLS = "id,kind,name,text,attrs,source,summary,topic_id,node_group,embedding"

    def get_node(self, node_id: str) -> Node | None:
        r = self._conn.execute(
            f"SELECT {self._COLS} FROM {self.N} WHERE tenant=%s AND id=%s",
            (self.tenant, node_id)).fetchone()
        return self._row(r) if r else None

    def all_nodes(self, kind: str | None = None, group: str | None = None) -> list[Node]:
        q = f"SELECT {self._COLS} FROM {self.N} WHERE tenant=%s"
        p = [self.tenant]
        if kind:
            q += " AND kind=%s"
            p.append(kind)
        if group is not None:
            q += " AND node_group=%s"
            p.append(group)
        return [self._row(r) for r in self._conn.execute(q, p).fetchall()]

    def search(self, vector: list[float], k: int = 10, kind: str | None = None,
               group: str | None = None) -> list[tuple[Node, float]]:
        q = (f"SELECT {self._COLS}, 1-(embedding<=>%s::vector) AS sim FROM {self.N} "
             f"WHERE tenant=%s AND embedding IS NOT NULL")
        p: list = [vector, self.tenant]
        if kind:
            q += " AND kind=%s"
            p.append(kind)
        if group is not None:
            q += " AND node_group=%s"
            p.append(group)
        q += " ORDER BY embedding<=>%s::vector LIMIT %s"
        p += [vector, k]
        return [(self._row(r), float(r[10])) for r in self._conn.execute(q, p).fetchall()]

    def delete_nodes(self, ids: list[str]) -> int:
        if not ids:
            return 0
        with self._conn.cursor() as cur:
            cur.execute(f"DELETE FROM {self.N} WHERE tenant=%s AND id = ANY(%s)",
                        (self.tenant, list(ids)))
            return cur.rowcount or 0

    def upsert_links(self, links: list[Link]) -> None:
        # Idempotent: replace any existing (src,dst,type) edge for this tenant, then
        # insert. A scheduled job re-sends all edges every run, so a plain INSERT would
        # grow the table without bound; delete-then-insert keeps it stable and needs no
        # unique constraint (works on pre-existing tables too). Dedupe the batch first.
        if not links:
            return
        dedup = {(l.src, l.dst, l.type): l for l in links}
        with self._conn.cursor() as cur:
            cur.executemany(
                f"DELETE FROM {self.L} WHERE tenant=%s AND src=%s AND dst=%s AND type=%s",
                [(self.tenant, s, d, t) for (s, d, t) in dedup])
            cur.executemany(
                f"INSERT INTO {self.L} (tenant,src,dst,type,weight,attrs) "
                f"VALUES (%s,%s,%s,%s,%s,%s)",
                [(self.tenant, l.src, l.dst, l.type, l.weight, json.dumps(l.attrs))
                 for l in dedup.values()])

    def links_for(self, node_id: str) -> list[Link]:
        rows = self._conn.execute(
            f"SELECT src,dst,type,weight,attrs FROM {self.L} WHERE tenant=%s AND "
            f"(src=%s OR dst=%s)", (self.tenant, node_id, node_id)).fetchall()
        return [Link(src=r[0], dst=r[1], type=r[2], weight=r[3], attrs=r[4] or {}) for r in rows]

    def upsert_topics(self, topics: list[Topic]) -> None:
        with self._conn.cursor() as cur:
            for t in topics:
                cur.execute(
                    f"INSERT INTO {self.T} (tenant,id,label,description,node_ids) "
                    f"VALUES (%s,%s,%s,%s,%s) ON CONFLICT (tenant,id) DO UPDATE SET "
                    f"label=EXCLUDED.label,description=EXCLUDED.description,"
                    f"node_ids=EXCLUDED.node_ids",
                    (self.tenant, t.id, t.label, t.description, json.dumps(t.node_ids)))

    def all_topics(self) -> list[Topic]:
        rows = self._conn.execute(
            f"SELECT id,label,description,node_ids FROM {self.T} WHERE tenant=%s",
            (self.tenant,)).fetchall()
        return [Topic(id=r[0], label=r[1], description=r[2] or "", node_ids=r[3] or []) for r in rows]
