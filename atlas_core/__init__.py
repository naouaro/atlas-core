"""Atlas Core — a domain-agnostic semantic knowledge map.

Ingest any content → embed → cluster into topics → summarize → narrate →
semantic search. Pluggable embedding/LLM providers and storage. Generalized from
a production code-graph engine so the same pipeline maps courses, articles, or
any data — not just code.
"""
from __future__ import annotations

from .engine.pipeline import Atlas
from .models import Link, Narrative, Node, Topic

__version__ = "0.1.0"
__all__ = ["Atlas", "Node", "Link", "Topic", "Narrative", "__version__"]
