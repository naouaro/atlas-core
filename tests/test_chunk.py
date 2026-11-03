from atlas_core import Atlas, chunk_text
from atlas_core.ingest.documents import DocumentIngester
from atlas_core.providers.local import LocalEmbeddingProvider, NullLLM


def test_chunk_text_bounds_and_edges():
    assert chunk_text("") == []
    assert chunk_text("short") == ["short"]
    long = ". ".join(f"cümle {i} içerik burada" for i in range(300))
    chunks = chunk_text(long, max_chars=200, overlap=40)
    assert len(chunks) > 1
    assert all(len(c) <= 200 + 40 for c in chunks)   # bounded (+ overlap slack)


def test_document_ingester_chunking_emits_children_and_links():
    docs = [
        {"id": "d1", "kind": "article", "title": "طويل", "text": "البند رقم واحد. " * 500},
        {"id": "d2", "kind": "article", "title": "قصير", "text": "سطر قصير"},
    ]
    ing = DocumentIngester(docs, chunk_chars=400)
    nodes = ing.nodes()
    links = ing.links()
    ids = {n.id for n in nodes}
    assert "d1" in ids and "d1#c0" in ids          # parent kept + chunk children
    assert "d2#c0" not in ids                        # short doc is not chunked
    chunk_nodes = [n for n in nodes if n.kind == "article_chunk"]
    assert chunk_nodes and all(n.attrs.get("parent") == "d1" for n in chunk_nodes)
    assert any(l.type == "chunk_of" and l.dst == "d1" for l in links)


def test_chunks_are_searchable():
    body = "مقدمة عامة هنا. " * 60 + " فقرة مميزة عن تصدير الشهادات رقمياً للطلاب. " + "خاتمة. " * 60
    docs = [{"id": "d1", "kind": "article", "title": "دليل", "text": body}]
    atlas = Atlas(embedder=LocalEmbeddingProvider(), llm=NullLLM())
    ing = DocumentIngester(docs, chunk_chars=300)
    atlas.ingest(ing.nodes(), ing.links())
    atlas.build()
    hits = atlas.search("تصدير الشهادات رقمياً", k=3, kind="article_chunk")
    assert hits   # the buried passage is retrievable as its own chunk
