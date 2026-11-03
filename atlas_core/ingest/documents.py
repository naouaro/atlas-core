"""atlas_core.ingest.documents — reference ingester for generic content.

Takes plain dicts and produces nodes + links. This is the shape most data
products use (courses, lessons, articles, FAQs, tickets). HTML is stripped to
text for embedding; `links` are passed through verbatim (derive them from your
own relations — e.g. a lesson's module_id → a `lesson_in_module` link).

    DocumentIngester([
        {"id": "c1", "kind": "course", "title": "...", "text": "...",
         "attrs": {...}, "source": "https://..."},
        ...
    ], links=[{"src": "l1", "dst": "m1", "type": "lesson_in_module"}])
"""
from __future__ import annotations

import re

from ..models import Link, Node
from .base import Ingester

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t\r\f\v]+")


def html_to_text(s: str) -> str:
    s = _TAG.sub(" ", s or "")
    s = s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return _WS.sub(" ", s).strip()


class DocumentIngester(Ingester):
    def __init__(self, docs: list[dict], links: list[dict] | None = None,
                 strip_html: bool = True):
        self._docs = docs or []
        self._links = links or []
        self._strip = strip_html

    def nodes(self) -> list[Node]:
        out: list[Node] = []
        for d in self._docs:
            text = d.get("text") or d.get("body") or ""
            if self._strip:
                text = html_to_text(text)
            out.append(Node(
                id=str(d["id"]),
                kind=str(d.get("kind") or "document"),
                name=str(d.get("title") or d.get("name") or d["id"]),
                text=text,
                attrs=dict(d.get("attrs") or {}),
                source=d.get("source"),
            ))
        return out

    def links(self) -> list[Link]:
        return [Link(src=str(l["src"]), dst=str(l["dst"]),
                     type=str(l.get("type") or "related"),
                     weight=float(l.get("weight", 1.0)),
                     attrs=dict(l.get("attrs") or {}))
                for l in self._links]
