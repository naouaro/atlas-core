"""atlas_core.engine.summarize / narrate — meaning layer over the nodes.

Per-node one-line summaries and a map-level narrative. Uses the LLM when
present; degrades to extractive/heuristic text when offline so nothing here
hard-requires model access.
"""
from __future__ import annotations

import re

from ..models import Narrative, Node, Topic

_SENT = re.compile(r"[^.!?؟\n]+[.!?؟]?", re.UNICODE)


def _first_sentence(text: str, limit: int = 200) -> str:
    text = (text or "").strip()
    m = _SENT.search(text)
    s = (m.group(0).strip() if m else text)
    return s[:limit].strip()


def summarize_nodes(nodes: list[Node], llm=None) -> None:
    """Fill `node.summary` in place."""
    offline = llm is None or getattr(llm, "offline", False)
    for n in nodes:
        if n.summary:
            continue
        if offline or not (n.text or "").strip():
            n.summary = _first_sentence(n.text) or n.name
        else:
            n.summary = llm.complete(
                f"In ONE sentence, say what this {n.kind} is about.\n\n"
                f"Title: {n.name}\nContent: {n.text[:2000]}",
                system="You write terse, factual one-line summaries.",
                max_tokens=80).strip() or _first_sentence(n.text) or n.name


def narrate(topics: list[Topic], nodes: list[Node], llm=None,
            scope: str = "map") -> Narrative:
    labels = [t.label for t in sorted(topics, key=lambda t: -len(t.node_ids))]
    heuristic = (f"This {scope} contains {len(nodes)} items across "
                 f"{len(topics)} topics: " + "، ".join(labels[:12]) + ".")
    offline = llm is None or getattr(llm, "offline", False)
    if offline or not labels:
        return Narrative(scope=scope, text=heuristic)
    try:
        text = llm.complete(
            f"Write a 3-5 sentence description of this {scope}. It has "
            f"{len(nodes)} items grouped into these topics: {', '.join(labels[:15])}. "
            f"Answer in the same language as the topic labels.",
            system="You write clear, concrete overviews. No hype.",
            max_tokens=400).strip()
    except Exception:
        text = ""
    # never return a blank narrative — fall back to the heuristic summary
    return Narrative(scope=scope, text=text or heuristic)
