"""atlas_core.ingest.sqldb — build a map straight from a relational database.

The key idea for *data* (vs code): you already know the structure — it's in your
schema. So nodes come from table rows and links come DETERMINISTICALLY from
foreign keys. No inference. Point this at your platform's DB with a small
mapping and you get the whole platform (courses · modules · lessons · articles …)
as one searchable, clustered, narrated map.

Works with any DB-API 2.0 connection (sqlite3, psycopg, mysqlclient …): it only
uses `cursor.execute` + `cursor.description`.

    SqlIngester(conn,
        tables={
          "courses": {"kind": "course", "id": "id", "name": "title",
                      "text": ["title", "description"], "source": "slug"},
          "lessons": {"kind": "lesson", "id": "id", "name": "title",
                      "text": ["title", "body"]},
        },
        links=[
          {"from": "lessons", "fk": "module_id", "to": "modules",
           "type": "lesson_in_module"},
          {"from": "modules", "fk": "course_id", "to": "courses",
           "type": "module_in_course"},
        ])

Node ids are namespaced `"<table>:<pk>"` so keys never collide across tables;
links reference the same namespaced ids.
"""
from __future__ import annotations

from typing import Any

from ..models import Link, Node
from .base import Ingester


def _rows(conn, sql: str) -> list[dict]:
    cur = conn.cursor()
    cur.execute(sql)
    cols = [d[0] for d in cur.description]
    out = [dict(zip(cols, r)) for r in cur.fetchall()]
    cur.close()
    return out


def _text(row: dict, cols) -> str:
    if isinstance(cols, str):
        cols = [cols]
    parts = [str(row.get(c)) for c in (cols or []) if row.get(c) not in (None, "")]
    return "\n".join(parts)


class SqlIngester(Ingester):
    def __init__(self, conn, tables: dict[str, dict], links: list[dict] | None = None):
        self.conn = conn
        self.tables = tables
        self._links = links or []

    def nodes(self) -> list[Node]:
        out: list[Node] = []
        for table, m in self.tables.items():
            id_col = m.get("id", "id")
            name_col = m.get("name", id_col)
            text_cols = m.get("text", [])
            source_col = m.get("source")
            group_col = m.get("group")  # e.g. "academyId" → node.group (sub-tenant scope)
            used = {id_col, name_col, source_col, group_col,
                    *(text_cols if isinstance(text_cols, list) else [text_cols])}
            sql = m.get("sql") or f"SELECT * FROM {table}"  # optional per-table override
            for row in _rows(self.conn, sql):
                pk = row.get(id_col)
                if pk is None:
                    continue
                attrs: dict[str, Any] = {k: v for k, v in row.items()
                                         if k not in used and _json_ok(v)}
                grp = row.get(group_col) if group_col else None
                out.append(Node(
                    id=f"{table}:{pk}",
                    kind=str(m.get("kind") or table),
                    name=str(row.get(name_col) or pk),
                    text=_text(row, text_cols),
                    attrs=attrs,
                    group=str(grp) if grp is not None else None,
                    source=str(row.get(source_col)) if source_col and row.get(source_col) else None,
                ))
        return out

    def links(self) -> list[Link]:
        out: list[Link] = []
        for rule in self._links:
            frm, fk, to = rule["from"], rule["fk"], rule["to"]
            typ = rule.get("type", "related")
            id_col = self.tables.get(frm, {}).get("id", "id")
            sql = rule.get("sql") or f"SELECT {id_col}, {fk} FROM {frm}"
            for row in _rows(self.conn, sql):
                src_pk, dst_pk = row.get(id_col), row.get(fk)
                if src_pk is None or dst_pk is None:
                    continue
                out.append(Link(src=f"{frm}:{src_pk}", dst=f"{to}:{dst_pk}", type=typ))
        return out


def _json_ok(v: Any) -> bool:
    return v is None or isinstance(v, (str, int, float, bool))
