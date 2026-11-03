"""Build a map directly from a relational DB (the #1 pattern for an LMS / knowledge base).

A tiny in-memory SQLite stands in for the platform DB: courses → modules →
lessons, linked by foreign keys. SqlIngester turns rows into nodes and FKs into
deterministic links; Atlas does the rest. Offline (no cloud) so it just runs:

    python examples/sqldb_demo.py
"""
import sqlite3

from atlas_core import Atlas
from atlas_core.ingest.sqldb import SqlIngester
from atlas_core.providers.local import LocalEmbeddingProvider, NullLLM

conn = sqlite3.connect(":memory:")
conn.executescript("""
CREATE TABLE courses (id INTEGER PRIMARY KEY, title TEXT, description TEXT, slug TEXT);
CREATE TABLE modules (id INTEGER PRIMARY KEY, course_id INTEGER, title TEXT);
CREATE TABLE lessons (id INTEGER PRIMARY KEY, module_id INTEGER, title TEXT, body TEXT);

INSERT INTO courses VALUES
 (1,'أساسيات تصميم الجرافيك','تعلّم مبادئ التصميم والألوان والتكوين','graphic-basics'),
 (2,'التسويق الرقمي للمبتدئين','حملات إعلانية وتحليلات وسوشال ميديا','digital-marketing');
INSERT INTO modules VALUES
 (10,1,'النظرية اللونية'),(11,1,'التكوين والتخطيط'),(12,2,'إعلانات ميتا'),(13,2,'تحليلات الأداء');
INSERT INTO lessons VALUES
 (100,10,'عجلة الألوان','شرح عجلة الألوان والتناسق اللوني'),
 (101,10,'التباين والتدرّج','استخدام التباين لإبراز العناصر'),
 (102,11,'شبكة التخطيط','تنظيم العناصر عبر الشبكة'),
 (103,12,'إنشاء حملة على فيسبوك','خطوات ضبط حملة إعلانية واستهداف الجمهور'),
 (104,13,'قراءة لوحة التحليلات','مؤشرات الأداء ومعدل التحويل');
""")

ing = SqlIngester(
    conn,
    tables={
        "courses": {"kind": "course", "id": "id", "name": "title",
                    "text": ["title", "description"], "source": "slug"},
        "modules": {"kind": "module", "id": "id", "name": "title", "text": ["title"]},
        "lessons": {"kind": "lesson", "id": "id", "name": "title", "text": ["title", "body"]},
    },
    links=[
        {"from": "lessons", "fk": "module_id", "to": "modules", "type": "lesson_in_module"},
        {"from": "modules", "fk": "course_id", "to": "courses", "type": "module_in_course"},
    ],
)

atlas = Atlas(embedder=LocalEmbeddingProvider(), llm=NullLLM())
nodes, links = ing.nodes(), ing.links()
atlas.ingest(nodes, links)
atlas.build()

print(f"nodes: {len(nodes)} (courses/modules/lessons) | links: {len(links)} (from FKs)")
print("\n== deterministic links (from foreign keys) ==")
for l in links:
    print(f"  {l.src}  --{l.type}-->  {l.dst}")
print("\n== topics ==")
for t in atlas.topics():
    print(f"  [{t.id}] {t.label} ({len(t.node_ids)})")
print("\n== semantic search: 'كيف أعمل حملة إعلانية؟' ==")
for n, s in atlas.search("كيف أعمل حملة إعلانية؟", k=3):
    print(f"  {s:.3f}  [{n.kind}] {n.name}")
print("\n== related to lesson 'عجلة الألوان' (lessons:100) ==")
for l in atlas.related("lessons:100"):
    print(f"  {l.src} --{l.type}--> {l.dst}")
