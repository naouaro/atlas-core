"""atlas_core.providers.openai — OpenAI embeddings + chat (optional).

`pip install atlas-core[openai]`. Key via OPENAI_API_KEY. `text-embedding-3-small`
is multilingual and cheap; swap `model` for -3-large if you want more quality.
"""
from __future__ import annotations

from .base import EmbeddingProvider, LLMProvider


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model: str = "text-embedding-3-small", dim: int = 1536):
        from openai import OpenAI  # noqa: PLC0415
        self._c = OpenAI()
        self._model = model
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        r = self._c.embeddings.create(model=self._model,
                                      input=[t[:8000] for t in texts])
        return [d.embedding for d in r.data]


class OpenAILLMProvider(LLMProvider):
    def __init__(self, model: str = "gpt-4o-mini"):
        from openai import OpenAI  # noqa: PLC0415
        self._c = OpenAI()
        self._model = model

    def complete(self, prompt: str, *, system: str | None = None,
                 max_tokens: int = 512) -> str:
        msgs = ([{"role": "system", "content": system}] if system else []) + \
               [{"role": "user", "content": prompt}]
        r = self._c.chat.completions.create(model=self._model, messages=msgs,
                                            max_tokens=max_tokens)
        return r.choices[0].message.content or ""
