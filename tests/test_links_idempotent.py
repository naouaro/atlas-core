from atlas_core.models import Link
from atlas_core.store.memory import InMemoryVectorStore


def test_links_idempotent_on_resync():
    s = InMemoryVectorStore()
    links = [Link("a", "b", "rel"), Link("b", "c", "rel")]
    s.upsert_links(links)
    s.upsert_links(links)   # a scheduled job re-sends the full edge set every run
    assert len(s.links_for("a")) == 1
    assert len(s.links_for("b")) == 2     # a->b and b->c, no duplicates
    assert len(s.links_for("c")) == 1
    # a changed weight replaces, doesn't append
    s.upsert_links([Link("a", "b", "rel", weight=2.0)])
    ab = [l for l in s.links_for("a") if l.dst == "b"]
    assert len(ab) == 1 and ab[0].weight == 2.0
