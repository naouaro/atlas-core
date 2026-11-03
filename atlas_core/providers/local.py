"""atlas_core.providers.local — zero-cloud providers so the engine runs offline.

`LocalEmbeddingProvider`:
  - if `sentence-transformers` is installed, uses a real MULTILINGUAL model
    (handles Arabic, Turkish, and other non-English content);
  - otherwise falls back to a deterministic hashed bag-of-tokens embedding so
    the library still imports, runs, and gives *some* semantic signal with no
    dependencies at all (good for CI, tests, and a clone-and-run demo).

`NullLLM`: a no-network LLM stand-in that produces a naive extractive summary /
label, so clustering + summaries + narratives work without any model access.
"""
from __future__ import annotations

import hashlib
import math

from ..textnorm import tokens as _tokens
from .base import EmbeddingProvider, LLMProvider

#: A compact, widely-available multilingual sentence model (Arabic, Turkish, +50 langs).
DEFAULT_ST_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class LocalEmbeddingProvider(EmbeddingProvider):
    def __init__(self, dim: int = 384, model: str | None = None):
        self._dim = dim
        self._st = None
        try:  # prefer a real multilingual model when available
            from sentence_transformers import SentenceTransformer  # noqa: PLC0415
            self._st = SentenceTransformer(model or DEFAULT_ST_MODEL)
            self._dim = self._st.get_sentence_embedding_dimension()
        except Exception:
            self._st = None  # fall back to the hashed embedding below

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self._st is not None:
            return [list(map(float, v)) for v in
                    self._st.encode(list(texts), normalize_embeddings=True)]
        return [self._hash_embed(t) for t in texts]

    def _hash_embed(self, text: str) -> list[float]:
        """Deterministic signed-hash bag-of-tokens, L2-normalized. Crude but
        order-independent and language-agnostic — similar texts land near each
        other. (A real model via sentence-transformers is strongly preferred.)"""
        vec = [0.0] * self._dim
        for tok in _tokens(text):
            h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
            idx = h % self._dim
            sign = 1.0 if (h >> 7) & 1 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]


class NullLLM(LLMProvider):
    """Offline stand-in: extractive 'summary' = first sentence; 'label' = the
    most frequent salient token. Keeps the pipeline fully runnable with no model."""

    offline = True  # engine honors this to take heuristic label/summary paths

    def complete(self, prompt: str, *, system: str | None = None,
                 max_tokens: int = 512) -> str:
        body = prompt.strip()
        # crude: return the first non-empty line, truncated
        for line in body.splitlines():
            line = line.strip()
            if line:
                return line[:240]
        return ""
