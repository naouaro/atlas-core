from atlas_core import Atlas, Glossary
from atlas_core.ingest.documents import DocumentIngester
from atlas_core.providers.local import LocalEmbeddingProvider, NullLLM
from atlas_core.textnorm import fold


def test_fold_handles_turkish_dotted_i():
    # İ (dotted capital I) and plain i must compare equal; folding is idempotent.
    assert fold("İstanbul") == fold("istanbul")
    assert fold("İSTANBUL") == fold("istanbul")
    assert fold("ŞÖĞÜÇ") == fold("şöğüç")
    assert fold(fold("İçerik")) == fold("İçerik")


def test_glossary_matches_across_turkish_casing():
    g = Glossary()
    g.add("sertifika", node_ids=["c1"],
          aliases=["İstanbul Kursu", "certificate"],
          definition="kurs tamamlama belgesi")
    # a query in different Turkish casing still resolves to the same entry
    # (dotted İ ↔ i — the common breakage str.lower() gets wrong)
    assert {e.term for e in g.resolve("SERTİFİKA nasıl verilir?")} == {"sertifika"}
    # alias lookup is İ-casing-insensitive
    assert g.get("İSTANBUL KURSU").term == "sertifika"
    # expansion injects the Turkish canonical + definition for an English query
    out = g.expand_query("how to get a certificate")
    assert "sertifika" in out and "kurs tamamlama belgesi" in out


def test_turkish_search_runs_and_ranks():
    docs = [
        {"id": "t1", "kind": "course", "title": "Dijital Pazarlama",
         "text": "reklam kampanyaları ve analiz"},
        {"id": "t2", "kind": "course", "title": "Grafik Tasarım",
         "text": "renk teorisi ve kompozisyon"},
    ]
    atlas = Atlas(embedder=LocalEmbeddingProvider(), llm=NullLLM())
    ing = DocumentIngester(docs)
    atlas.ingest(ing.nodes(), ing.links())
    atlas.build()
    hits = atlas.search("dijital pazarlama reklam", k=2)
    assert hits
    assert hits[0][0].id == "t1"   # marketing course outranks design on meaning/overlap
