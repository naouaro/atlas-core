from atlas_core import Atlas
from atlas_core.ingest.documents import DocumentIngester
from atlas_core.providers.local import LocalEmbeddingProvider, NullLLM


def _atlas(docs):
    a = Atlas(embedder=LocalEmbeddingProvider(), llm=NullLLM())
    ing = DocumentIngester(docs)
    a.ingest(ing.nodes(), ing.links())
    a.build()
    return a


def test_hybrid_boosts_exact_terms_and_caps_k():
    docs = [
        {"id": "a", "kind": "doc", "title": "فاتورة ضريبية", "text": "حساب الضريبة على الفواتير"},
        {"id": "b", "kind": "doc", "title": "تصميم جرافيك", "text": "الألوان والتكوين"},
        {"id": "c", "kind": "doc", "title": "تسويق رقمي", "text": "حملات وتحليلات"},
    ]
    atlas = _atlas(docs)
    hits = atlas.search("فاتورة ضريبية", k=2, hybrid=True)
    assert hits and hits[0][0].id == "a"   # exact-term doc wins on the lexical blend
    assert len(hits) <= 2
