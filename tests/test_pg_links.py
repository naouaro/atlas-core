"""Postgres link-key tests. Run against a throwaway pgvector database:

    docker run -d --rm -p 55432:5432 -e POSTGRES_PASSWORD=t pgvector/pgvector:pg17
    ATLAS_TEST_PG_DSN=postgresql://postgres:t@localhost:55432/postgres pytest tests/test_pg_links.py

Skipped when ATLAS_TEST_PG_DSN is not set.
"""
import os
import uuid

import pytest

from atlas_core.models import Link, Node

DSN = os.environ.get("ATLAS_TEST_PG_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="ATLAS_TEST_PG_DSN not set")


def _store(prefix, tenant="t1"):
    from atlas_core.store.postgres import PgVectorStore
    return PgVectorStore(DSN, dim=3, tenant=tenant, table_prefix=prefix)


def _count(store):
    return store._conn.execute(f"SELECT count(*) FROM {store.L}").fetchone()[0]


@pytest.fixture
def prefix():
    p = "t_" + uuid.uuid4().hex[:8]
    yield p
    import psycopg
    with psycopg.connect(DSN, autocommit=True) as c:
        for t in ("nodes", "links", "topics"):
            c.execute(f"DROP TABLE IF EXISTS {p}_{t}")


def test_resync_never_grows(prefix):
    s = _store(prefix)
    links = [Link("a", "b", "rel"), Link("b", "c", "rel"), Link("a", "b", "rel")]
    for _ in range(5):                       # five scheduled runs
        s.upsert_links(links)
    assert _count(s) == 2
    s.upsert_links([Link("a", "b", "rel", weight=3.0)])
    ab = [l for l in s.links_for("a") if l.dst == "b"]
    assert len(ab) == 1 and ab[0].weight == 3.0


def test_legacy_duplicates_collapsed_on_open(prefix):
    s = _store(prefix)
    # simulate a table written by an older version: no key, same edge x100
    s._conn.execute(f"DROP INDEX {prefix}_links_uq")
    for _ in range(100):
        s._conn.execute(f"INSERT INTO {prefix}_links VALUES ('t1','a','b','rel',1.0,'{{}}')")
        s._conn.execute(f"INSERT INTO {prefix}_links VALUES ('t2','a','b','rel',1.0,'{{}}')")
    assert _count(s) == 200
    s2 = _store(prefix)                      # reopening migrates
    assert _count(s2) == 2                   # one per tenant — tenants stay separate
    s2.upsert_links([Link("a", "b", "rel")])
    assert _count(s2) == 2


def test_tenants_isolated(prefix):
    a, b = _store(prefix, "A"), _store(prefix, "B")
    a.upsert_links([Link("x", "y", "rel")])
    b.upsert_links([Link("x", "y", "rel")])
    assert _count(a) == 2
    assert len(a.links_for("x")) == 1 and len(b.links_for("x")) == 1


def test_prune_drops_dangling_links(prefix):
    s = _store(prefix)
    s.upsert_nodes([Node("a", "k", "a", embedding=[1.0, 0.0, 0.0]),
                    Node("b", "k", "b", embedding=[0.0, 1.0, 0.0])])
    s.upsert_links([Link("a", "b", "rel")])
    assert s.delete_nodes(["b"]) == 1
    assert s.links_for("a") == []
