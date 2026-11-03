import sqlite3

from atlas_core.ingest.sqldb import SqlIngester


def _conn():
    c = sqlite3.connect(":memory:")
    c.executescript("""
    CREATE TABLE courses (id INTEGER PRIMARY KEY, title TEXT, description TEXT);
    CREATE TABLE lessons (id INTEGER PRIMARY KEY, course_id INTEGER, title TEXT, body TEXT, mins INTEGER);
    INSERT INTO courses VALUES (1,'دورة','وصف');
    INSERT INTO lessons VALUES (10,1,'درس','محتوى',7),(11,1,'درس2','محتوى2',12);
    """)
    return c


def test_nodes_namespaced_and_mapped():
    ing = SqlIngester(_conn(), tables={
        "courses": {"kind": "course", "id": "id", "name": "title", "text": ["title", "description"]},
        "lessons": {"kind": "lesson", "id": "id", "name": "title", "text": ["title", "body"]},
    })
    nodes = {n.id: n for n in ing.nodes()}
    assert "courses:1" in nodes and "lessons:10" in nodes
    assert nodes["lessons:10"].kind == "lesson"
    assert "درس" in nodes["lessons:10"].text and "محتوى" in nodes["lessons:10"].text
    # non-mapped scalar columns land in attrs
    assert nodes["lessons:10"].attrs.get("mins") == 7


def test_links_from_foreign_keys():
    ing = SqlIngester(_conn(),
        tables={"courses": {"kind": "course", "id": "id", "name": "title"},
                "lessons": {"kind": "lesson", "id": "id", "name": "title"}},
        links=[{"from": "lessons", "fk": "course_id", "to": "courses", "type": "lesson_in_course"}])
    links = ing.links()
    assert len(links) == 2
    assert all(l.type == "lesson_in_course" for l in links)
    assert {l.src for l in links} == {"lessons:10", "lessons:11"}
    assert all(l.dst == "courses:1" for l in links)
