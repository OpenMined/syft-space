"""The HTML document an API-backed source hands to the chunker.

Title as an ``<h1>``, a byline, then the body. The heading names every
chunk of a long article; the byline puts the author, date, and tags into
the first chunk's text, where metadata alone would only be filterable.
"""

from __future__ import annotations

import html
from typing import Any

UNTITLED = "(untitled)"


def byline(metadata: dict[str, Any]) -> str:
    """``<p>By X. Published YYYY-MM-DD. Tags: a, b.</p>``, parts omitted
    when absent; empty when all are."""
    parts: list[str] = []
    if author := metadata.get("author"):
        parts.append(f"By {html.escape(author)}")
    if published := metadata.get("published"):
        parts.append(f"Published {published.date().isoformat()}")
    if tags := metadata.get("tags"):
        parts.append("Tags: " + ", ".join(html.escape(t) for t in tags))
    return f"<p>{'. '.join(parts)}.</p>" if parts else ""


def article_html(title: str, body: str, metadata: dict[str, Any]) -> str:
    """Assemble the document. ``title`` and ``body`` are the source's HTML,
    passed through; an empty body leaves only the heading and byline."""
    parts = [f"<h1>{title or UNTITLED}</h1>"]
    if line := byline(metadata):
        parts.append(line)
    if body:
        parts.append(body)
    return "\n".join(parts)
