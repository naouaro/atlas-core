"""atlas_core.engine.cluster — topic discovery over node embeddings.

K-means over the embeddings (a standard topic-discovery approach), then
label each cluster. Labels come from the LLM when one is available; otherwise a
deterministic heuristic (most salient shared token) keeps it fully offline.
"""
from __future__ import annotations

import re
from collections import Counter

import numpy as np

from ..models import Node, Topic
from ..textnorm import fold

_TOKEN = re.compile(r"[^\W_]{3,}", re.UNICODE)


def _auto_k(n: int) -> int:
    return max(2, min(n // 5, 12))


def _heuristic_label(names: list[str]) -> str:
    c: Counter = Counter()
    for nm in names:
        for t in _TOKEN.findall(fold(nm or "")):
            c[t] += 1
    common = [w for w, _ in c.most_common(3)]
    return " / ".join(common) if common else "topic"


def cluster_nodes(nodes: list[Node], llm=None, k: int | None = None,
                  group: str | None = None) -> list[Topic]:
    pool = [n for n in nodes if n.embedding is not None]
    if len(pool) < 4:
        t = Topic(id=0, label=_heuristic_label([n.name for n in pool]),
                  node_ids=[n.id for n in pool], group=group)
        for n in pool:
            n.topic_id = 0
        return [t] if pool else []

    k = k or _auto_k(len(pool))
    mat = np.asarray([n.embedding for n in pool], dtype=np.float32)
    # MiniBatchKMeans for large maps: bounded memory + far faster, negligible quality
    # loss at these cluster counts. (Memory at scale is dominated by holding the node
    # vectors here, not the fit — mini-batch keeps the fit itself cheap.)
    if len(pool) > 10_000:
        from sklearn.cluster import MiniBatchKMeans  # noqa: PLC0415
        km = MiniBatchKMeans(n_clusters=k, n_init=3, random_state=42, batch_size=2048)
    else:
        from sklearn.cluster import KMeans  # noqa: PLC0415
        km = KMeans(n_clusters=k, n_init=10, random_state=42)
    labels = km.fit_predict(mat)

    topics: list[Topic] = []
    offline = llm is None or getattr(llm, "offline", False)
    for cid in range(k):
        members = [pool[i] for i in range(len(pool)) if labels[i] == cid]
        if not members:
            continue
        names = [m.name for m in members]
        heur = _heuristic_label(names)
        if offline:
            label = heur
        else:
            titles = "\n".join(f"- {m.name}" for m in members[:25])
            label = (llm.complete(
                f"Give a 2-4 word topic label for this group of items:\n{titles}",
                system="You label clusters. Reply with ONLY the short label.",
                max_tokens=16).strip() or heur)
        t = Topic(id=cid, label=label[:80], node_ids=[m.id for m in members], group=group)
        for m in members:
            m.topic_id = cid
        topics.append(t)
    return topics
