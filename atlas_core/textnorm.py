"""atlas_core.textnorm — multilingual-safe text folding for matching.

Python's ``str.lower()`` mishandles Turkish casing: ``"İ".lower()`` yields ``"i̇"``
(an ``i`` plus a COMBINING DOT ABOVE, U+0307) and ``"I".lower()`` yields ``"i"``
rather than ``"ı"`` — so case-insensitive matching on Turkish text silently fails.

``fold()`` applies NFKC + ``casefold()`` and strips the combining dot above, so the
common Turkish forms (``İ``/``i``, ``I``/``i``) compare equal, alongside Arabic and
Latin. It is meant for substring/equality matching (glossary terms, cluster-label
tokens), NOT for display. Full locale-aware Turkish casing (``I``↔``ı``) is out of
scope — declare glossary aliases if you need that exact distinction.
"""
from __future__ import annotations

import re
import unicodedata

_COMBINING_DOT_ABOVE = "̇"
_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)  # letter/digit runs across scripts


def fold(s: str) -> str:
    """Case-insensitive, Turkish-safe normal form for matching."""
    if not s:
        return ""
    return unicodedata.normalize("NFKC", s).casefold().replace(_COMBINING_DOT_ABOVE, "")


def tokens(text: str, min_len: int = 1) -> list[str]:
    """Folded letter/digit tokens (script-agnostic: Arabic, Turkish, Latin …)."""
    return [t for t in (fold(m) for m in _TOKEN.findall(text or "")) if len(t) >= min_len]
