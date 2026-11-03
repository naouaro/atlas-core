"""atlas_core.providers.base — pluggable embedding + LLM interfaces.

The original engine was hard-wired to AWS Bedrock (Titan + Claude). For a
standalone/OSS engine that is a non-starter, so the provider is an interface:
ship Bedrock, OpenAI, and a zero-dependency Local implementation, and let a
user drop in their own. The engine only ever talks to these two ABCs.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """Turns text into fixed-dimension vectors for semantic search/clustering."""

    @property
    @abstractmethod
    def dim(self) -> int:
        """Vector dimensionality (stable for the life of the provider)."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Implementations SHOULD L2-normalize so cosine
        similarity == dot product. Order of the returned list matches input."""


class LLMProvider(ABC):
    """Generates short text: cluster labels, per-node summaries, narratives.

    Optional in practice — the engine degrades to heuristic labels/summaries
    when given :class:`atlas_core.providers.local.NullLLM`, so the whole
    pipeline runs with no model access at all."""

    @abstractmethod
    def complete(self, prompt: str, *, system: str | None = None,
                 max_tokens: int = 512) -> str:
        """Return the model's text completion for a single prompt."""
