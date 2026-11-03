"""atlas_core.providers.bedrock — AWS Bedrock embeddings + LLM.

Titan v2 for embeddings (1024-dim, normalized) and a Claude model for text.
`pip install atlas-core[bedrock]` (boto3). Credentials via the standard AWS
chain (env/profile/role).
"""
from __future__ import annotations

import json

from .base import EmbeddingProvider, LLMProvider

TITAN_V2 = "amazon.titan-embed-text-v2:0"
DEFAULT_CLAUDE = "anthropic.claude-3-5-haiku-20241022-v1:0"


def _client(region: str | None):
    import boto3  # noqa: PLC0415
    from botocore.config import Config  # noqa: PLC0415
    return boto3.client("bedrock-runtime", region_name=region,
                        config=Config(read_timeout=120, retries={"max_attempts": 3}))


class BedrockEmbeddingProvider(EmbeddingProvider):
    def __init__(self, region: str | None = None, model: str = TITAN_V2,
                 dim: int = 1024, max_workers: int = 8):
        self._c = _client(region)
        self._model = model
        self._dim = dim
        self._workers = max(1, max_workers)

    @property
    def dim(self) -> int:
        return self._dim

    def _one(self, text: str) -> list[float]:
        body = json.dumps({"inputText": (text or " ")[:8000], "dimensions": self._dim,
                           "normalize": True})
        r = self._c.invoke_model(modelId=self._model, body=body)
        return json.loads(r["body"].read())["embedding"]

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self._workers == 1 or len(texts) <= 1:
            return [self._one(t) for t in texts]
        from concurrent.futures import ThreadPoolExecutor  # noqa: PLC0415
        with ThreadPoolExecutor(max_workers=self._workers) as ex:
            return list(ex.map(self._one, texts))  # order preserved


class BedrockLLMProvider(LLMProvider):
    def __init__(self, region: str | None = None, model: str = DEFAULT_CLAUDE):
        self._c = _client(region)
        self._model = model

    def complete(self, prompt: str, *, system: str | None = None,
                 max_tokens: int = 512) -> str:
        body = {"anthropic_version": "bedrock-2023-05-31", "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}]}
        if system:
            body["system"] = system
        r = self._c.invoke_model(modelId=self._model, body=json.dumps(body))
        data = json.loads(r["body"].read())
        return "".join(b.get("text", "") for b in data.get("content", []))
