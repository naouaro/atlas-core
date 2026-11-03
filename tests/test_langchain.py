import pytest

pytest.importorskip("langchain_core")  # skip cleanly when the extra isn't installed

from atlas_core import Atlas  # noqa: E402
from atlas_core.ingest.documents import DocumentIngester  # noqa: E402
from atlas_core.integrations.langchain import atlas_search_tool  # noqa: E402
from atlas_core.providers.local import LocalEmbeddingProvider, NullLLM  # noqa: E402


def _atlas():
    docs = [
        {"id": "c1", "kind": "course", "title": "أساسيات التصميم",
         "text": "مبادئ التصميم والألوان", "source": "design-basics"},
        {"id": "c2", "kind": "course", "title": "التسويق الرقمي",
         "text": "حملات إعلانية وتحليلات"},
    ]
    a = Atlas(embedder=LocalEmbeddingProvider(), llm=NullLLM())
    ing = DocumentIngester(docs)
    a.ingest(ing.nodes(), ing.links())
    a.build()
    return a


def test_tool_builds_and_runs():
    tool = atlas_search_tool(_atlas(), kind="course", k=2)
    assert tool.name == "atlas_search"
    assert tool.description
    out = tool.invoke({"query": "تصميم"})
    assert isinstance(out, str) and out.strip()


def test_tool_respects_per_call_overrides():
    tool = atlas_search_tool(_atlas(), k=5)
    out = tool.invoke({"query": "تسويق", "k": 1, "kind": "course"})
    # k=1 → exactly one formatted line
    assert isinstance(out, str) and len(out.strip().splitlines()) == 1
