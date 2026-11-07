"""Template ingest+sync job — EDIT THIS to your schema, then deploy.

The handler imports `run()` from here. It reads from a relational source, maps rows
to nodes and foreign keys to links (via SqlIngester), and incrementally syncs into a
pgvector store. This is a TEMPLATE: the table/link mapping below is illustrative —
replace it with your own tables, and swap the source driver if you are not on
SQL Server.

Env:
    SOURCE_DSN    your source DB DSN (here: SQL Server, read-only)
    ATLAS_PG_DSN  postgresql://…  (the pgvector store)
    COURSE_LIMIT  0 = full catalog; N = newest N (fast verification run)
    AWS_REGION    region for Bedrock Titan/Claude (e.g. us-east-1)

Run directly for the one-time backfill:  python sync_job.py
"""
import os

from atlas_core import Atlas
from atlas_core.ingest.sqldb import SqlIngester
from atlas_core.providers.bedrock import BedrockEmbeddingProvider, BedrockLLMProvider
from atlas_core.providers.local import NullLLM

TENANT = os.environ.get("ATLAS_TENANT", "default")


def _connect(dsn: str):
    """Open your source connection. Any DB-API 2.0 connection works; this template
    parses a SQL Server-style DSN. Replace with psycopg/sqlite3/etc. as needed."""
    import re

    import pymssql  # noqa: PLC0415  (swap for your driver)
    p = dict(re.findall(r"(\w+)=([^;]+)", dsn))
    host, port = (p["Server"].split(",") + ["1433"])[:2]
    return pymssql.connect(server=host, port=int(port), user=p["User"],
                           password=p["Password"], database=p["Database"],
                           login_timeout=20, timeout=600)


def _ingester(conn, limit: int) -> SqlIngester:
    # EDIT: your tables → nodes, your foreign keys → links.
    return SqlIngester(conn, tables={
        "courses": {"kind": "course", "id": "id", "name": "title",
                    "text": ["title", "description"]},
        "lessons": {"kind": "lesson", "id": "id", "name": "title",
                    "text": ["title", "body"]},
    }, links=[
        {"from": "lessons", "fk": "course_id", "to": "courses", "type": "lesson_in_course"},
    ])


def run() -> dict:
    src, pg = os.environ["SOURCE_DSN"], os.environ["ATLAS_PG_DSN"]
    limit = int(os.environ.get("COURSE_LIMIT", "0"))
    region = os.environ.get("AWS_REGION", "us-east-1")

    conn = _connect(src)
    ing = _ingester(conn, limit)
    nodes, links = ing.nodes(), ing.links()

    emb = BedrockEmbeddingProvider(region=region, max_workers=12)
    from atlas_core.store.postgres import PgVectorStore  # noqa: PLC0415
    store = PgVectorStore(dsn=pg, dim=emb.dim, tenant=TENANT)
    try:
        llm = BedrockLLMProvider(region=region)
    except Exception:
        llm = NullLLM()

    atlas = Atlas(embedder=emb, store=store, llm=llm)
    stats = atlas.sync(nodes, links)   # embeds only changed/new; reuses unchanged
    if stats["changed"] or not store.all_topics():
        atlas.cluster()                # re-cluster/narrate only when content moved
        atlas.narrate()
    return stats


if __name__ == "__main__":
    print(run())
