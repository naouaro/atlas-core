"""Atlas Core — a domain-agnostic semantic knowledge map.

Ingest any content → embed → cluster into topics → summarize → narrate →
semantic search. Pluggable embedding/LLM providers and storage. Generalized from
a production code-graph engine so the same pipeline maps courses, articles, or
any data — not just code.
"""
from __future__ import annotations

from .chunk import chunk_text
from .engine.glossary import Glossary, GlossaryEntry
from .engine.pipeline import Atlas
from .models import Link, Narrative, Node, Topic

__version__ = "0.2.1"
__all__ = ["Atlas", "Node", "Link", "Topic", "Narrative",
           "Glossary", "GlossaryEntry", "chunk_text", "__version__"]
