"""atlas_core.integrations.langchain — expose an Atlas as a LangChain tool.

    pip install "atlas-core[langchain]"

    from atlas_core.integrations.langchain import atlas_search_tool
    tool = atlas_search_tool(atlas, kind="course")
    # drop `tool` into any LangChain / LangGraph agent's tool list.

The tool wraps `atlas.search`: an agent calls it with a natural-language query and
gets back the most relevant items by meaning, ready to ground its answer.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:  # avoid importing heavy/optional deps at module import time
    from ..engine.glossary import Glossary
    from ..engine.pipeline import Atlas


def atlas_search_tool(atlas: "Atlas", *, name: str = "atlas_search",
                      description: str | None = None, k: int = 5,
                      kind: str | None = None, group: str | None = None,
                      expand: "Glossary | None" = None, include_source: bool = True):
    """Build a LangChain ``StructuredTool`` over ``atlas.search``.

    ``k``/``kind``/``group``/``expand`` are the defaults baked into the tool; the
    agent may override ``k`` and ``kind`` per call. Requires ``langchain-core``
    (the ``[langchain]`` extra).
    """
    try:
        from langchain_core.tools import StructuredTool
    except ImportError as e:  # pragma: no cover - exercised only without the extra
        raise ImportError(
            "atlas_core.integrations.langchain needs langchain-core — install with: "
            'pip install "atlas-core[langchain]"') from e

    default_k, default_kind = k, kind

    def _search(query: str, k: int = default_k, kind: Optional[str] = default_kind) -> str:
        """Semantic search over the knowledge map. `query` is natural language (any
        language); `kind` optionally restricts to a node type (e.g. 'course')."""
        hits = atlas.search(query, k=k, kind=kind, group=group, expand=expand)
        if not hits:
            return "No matches."
        lines = []
        for node, score in hits:
            line = f"[{score:.3f}] ({node.kind}) {node.name}"
            if include_source and getattr(node, "source", None):
                line += f" — {node.source}"
            lines.append(line)
        return "\n".join(lines)

    return StructuredTool.from_function(
        func=_search,
        name=name,
        description=description or (
            "Semantic search over the Atlas knowledge map. Returns the most relevant "
            "items by meaning — use it to ground answers in real content."),
    )
