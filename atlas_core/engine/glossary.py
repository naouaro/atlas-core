"""atlas_core.engine.glossary — business-term ↔ node mapping.

Declare your domain vocabulary and tie each term (plus aliases / synonyms) to one
or more nodes. Two uses:

  1. ``resolve(text)`` — which declared terms appear in a piece of text (a user
     query, a document) and the nodes they point to. Deterministic case-insensitive
     match, language-agnostic (Arabic / English / mixed), no model needed.
  2. ``expand_query(query)`` — enrich a search query with the canonical term(s) and
     short definitions of any vocabulary it mentions, so the embedder gets a
     stronger, disambiguated signal before it hits the vector store. Pass the
     glossary straight to ``Atlas.search(query, expand=glossary)``.

Pure-Python, offline, JSON-serialisable (``to_dict`` / ``from_dict``). It does not
touch the store, so there is no schema change — persist it however you like.

Matching is substring-based, so declare terms specific enough not to collide (a
2-letter term can match inside unrelated words).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class GlossaryEntry:
    """A business term, its surface forms, and the nodes it denotes."""
    term: str
    node_ids: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    definition: str = ""


class Glossary:
    def __init__(self) -> None:
        self._entries: dict[str, GlossaryEntry] = {}   # canonical(lower) -> entry
        self._surface: dict[str, str] = {}             # term/alias(lower) -> canonical(lower)

    def add(self, term: str, node_ids: list[str] | None = None,
            aliases: tuple[str, ...] | list[str] = (), definition: str = "") -> GlossaryEntry:
        """Add/extend a term. Re-adding the same term merges node_ids/aliases."""
        canon = (term or "").strip()
        if not canon:
            raise ValueError("term must be non-empty")
        key = canon.lower()
        entry = self._entries.get(key)
        if entry is None:
            entry = GlossaryEntry(term=canon)
            self._entries[key] = entry
            self._surface[key] = key
        for nid in (node_ids or []):
            if nid not in entry.node_ids:
                entry.node_ids.append(nid)
        for a in aliases:
            a = (a or "").strip()
            if a and a not in entry.aliases:
                entry.aliases.append(a)
                self._surface[a.lower()] = key
        if definition:
            entry.definition = definition
        return entry

    def __len__(self) -> int:
        return len(self._entries)

    def entries(self) -> list[GlossaryEntry]:
        return list(self._entries.values())

    def get(self, term: str) -> GlossaryEntry | None:
        """Look up an entry by its canonical term OR any alias."""
        key = self._surface.get((term or "").strip().lower())
        return self._entries.get(key) if key else None

    def resolve(self, text: str) -> list[GlossaryEntry]:
        """Declared terms/aliases that appear (case-insensitive) in ``text``."""
        low = (text or "").lower()
        found: dict[str, GlossaryEntry] = {}
        for surface, canon in self._surface.items():
            if surface and surface in low:
                found[canon] = self._entries[canon]
        return list(found.values())

    def terms_for_node(self, node_id: str) -> list[str]:
        """Reverse lookup: which canonical terms point at this node."""
        return [e.term for e in self._entries.values() if node_id in e.node_ids]

    def expand_query(self, query: str) -> str:
        """Append the canonical term + definition of any vocabulary the query
        mentions, to strengthen the retrieval signal. No match → query unchanged."""
        hits = self.resolve(query)
        if not hits:
            return query
        extra: list[str] = []
        for e in hits:
            if e.term.lower() not in (query or "").lower():
                extra.append(e.term)
            if e.definition:
                extra.append(e.definition)
        return f"{query} — {' · '.join(extra)}" if extra else query

    def to_dict(self) -> dict:
        return {"entries": [{"term": e.term, "node_ids": e.node_ids,
                             "aliases": e.aliases, "definition": e.definition}
                            for e in self._entries.values()]}

    @classmethod
    def from_dict(cls, d: dict | None) -> "Glossary":
        g = cls()
        for e in (d or {}).get("entries", []):
            g.add(e["term"], node_ids=e.get("node_ids"),
                  aliases=e.get("aliases", ()), definition=e.get("definition", ""))
        return g
