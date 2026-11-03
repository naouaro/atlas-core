"""atlas_core.chunk — split long text into overlapping chunks for finer retrieval.

Embedding a whole long document dilutes its vector and (for Bedrock Titan) gets
truncated at ~8k chars, so a passage deep inside a long transcript becomes
unfindable. ``chunk_text`` splits language-agnostically: it prefers to break on
blank lines, then sentence enders (incl. the Arabic ``؟``), falling back to a hard
character cut, with a small overlap so a point split across a boundary is still
retrievable from both sides.
"""
from __future__ import annotations

import re

_PARA = re.compile(r"\n\s*\n")
_SENT = re.compile(r"(?<=[.!?؟])\s+")


def chunk_text(text: str, max_chars: int = 1500, overlap: int = 150) -> list[str]:
    """Greedy, overlap-aware chunks of at most ~``max_chars`` characters."""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    atoms: list[str] = []
    for para in _PARA.split(text):
        para = para.strip()
        if not para:
            continue
        if len(para) <= max_chars:
            atoms.append(para)
            continue
        for s in _SENT.split(para):
            s = s.strip()
            if not s:
                continue
            if len(s) > max_chars:                      # one over-long sentence → hard cut
                atoms += [s[i:i + max_chars] for i in range(0, len(s), max_chars)]
            else:
                atoms.append(s)

    chunks: list[str] = []
    buf = ""
    for a in atoms:
        if buf and len(buf) + 1 + len(a) > max_chars:
            chunks.append(buf)
            tail = buf[-overlap:] if overlap else ""
            buf = f"{tail} {a}".strip()
        else:
            buf = f"{buf} {a}".strip() if buf else a
    if buf:
        chunks.append(buf)
    return chunks
