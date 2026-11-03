from atlas_core import Atlas, Glossary
from atlas_core.ingest.documents import DocumentIngester
from atlas_core.providers.local import LocalEmbeddingProvider, NullLLM


def test_resolve_aliases_and_reverse_lookup():
    g = Glossary()
    g.add("شهادة", node_ids=["a1"], aliases=["certificate", "سيرتفيكيت"],
          definition="وثيقة إتمام الدورة")
    g.add("دفع", node_ids=["a3"], aliases=["payment", "Stripe"])

    # canonical (Arabic) found
    assert any(e.term == "شهادة" for e in g.resolve("كيف أعطي الطالب شهادة؟"))
    # alias (English, case-insensitive) resolves to the Arabic canonical
    assert {e.term for e in g.resolve("set up STRIPE payment")} == {"دفع"}
    # reverse lookup + alias get()
    assert "شهادة" in g.terms_for_node("a1")
    assert g.get("certificate").term == "شهادة"
    assert g.get("unknown") is None


def test_expand_query_injects_canonical_and_definition():
    g = Glossary()
    g.add("سيرتفيكيت", node_ids=["a1"], aliases=["certificate"],
          definition="شهادة إتمام الدورة")
    out = g.expand_query("how do I issue a certificate?")
    assert "سيرتفيكيت" in out and "شهادة إتمام الدورة" in out
    # no vocabulary in the query → unchanged
    assert g.expand_query("random unrelated text") == "random unrelated text"


def test_roundtrip_serialisation():
    g = Glossary()
    g.add("دفع", node_ids=["a3"], aliases=["payment"], definition="بوابة الدفع")
    g2 = Glossary.from_dict(g.to_dict())
    assert len(g2) == len(g)
    assert g2.get("payment").term == "دفع"
    assert g2.get("payment").definition == "بوابة الدفع"


def test_expand_plugs_into_atlas_search():
    docs = [
        {"id": "a1", "kind": "article", "title": "إصدار الشهادات",
         "text": "منح شهادة إتمام الدورة للطالب"},
        {"id": "a2", "kind": "article", "title": "الدفع",
         "text": "بوابة الدفع واستلام الأرباح"},
    ]
    atlas = Atlas(embedder=LocalEmbeddingProvider(), llm=NullLLM())
    ing = DocumentIngester(docs)
    atlas.ingest(ing.nodes(), ing.links())
    atlas.build()

    g = Glossary()
    g.add("سيرتفيكيت", node_ids=["a1"], aliases=["certificate"],
          definition="شهادة إتمام الدورة للطالب")
    # passing the glossary must not break search and still returns results
    hits = atlas.search("certificate", k=2, expand=g)
    assert hits and all(isinstance(s, float) for _, s in hits)
