from atlas_core import Atlas, Node
from atlas_core.ingest.documents import DocumentIngester, html_to_text
from atlas_core.providers.local import LocalEmbeddingProvider, NullLLM
from atlas_core.store.memory import InMemoryVectorStore


def _atlas():
    docs = [
        {"id": str(i), "kind": "article", "title": t, "text": t}
        for i, t in enumerate([
            "إصدار الشهادات للطلاب", "منح الشهادة يدوياً", "قالب الشهادة",
            "الربط مع بوابة دفع Stripe", "طرق استلام الإيرادات", "الحسابات البنكية",
            "إنشاء دورة جديدة", "رفع الدروس والفيديوهات", "تسعير الدورات",
        ])
    ]
    a = Atlas(embedder=LocalEmbeddingProvider(), store=InMemoryVectorStore(), llm=NullLLM())
    ing = DocumentIngester(docs)
    a.ingest(ing.nodes())
    a.build()
    return a


def test_embed_all_fills_vectors():
    a = _atlas()
    assert all(n.embedding is not None for n in a.store.all_nodes())


def test_search_is_semantic_ish():
    a = _atlas()
    hits = a.search("شهادة الطالب", k=3)
    assert hits, "search returned nothing"
    titles = " ".join(n.name for n, _ in hits)
    assert "شهاد" in titles  # a certificate article ranks in the top-3


def test_clustering_produces_topics():
    a = _atlas()
    topics = a.topics()
    assert len(topics) >= 2
    assert sum(len(t.node_ids) for t in topics) == len(a.store.all_nodes())


def test_summaries_and_narrative():
    a = _atlas()
    assert all(n.summary for n in a.store.all_nodes())
    assert a.narrative and a.narrative.text


def test_html_to_text():
    assert html_to_text("<p>مرحبا <b>بك</b></p>") == "مرحبا بك"


def test_links_roundtrip():
    a = Atlas(embedder=LocalEmbeddingProvider(), llm=NullLLM())
    a.ingest([Node(id="x", kind="a", name="X"), Node(id="y", kind="a", name="Y")],
             DocumentIngester([], [{"src": "x", "dst": "y", "type": "prereq_of"}]).links())
    rel = a.related("x")
    assert rel and rel[0].type == "prereq_of"
