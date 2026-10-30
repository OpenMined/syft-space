"""YAML front matter in Markdown files.

Article producers prefix each ``.md`` file with a ``---`` delimited header
(title, source, author, url, dates, ...). It describes the document rather
than being part of it, so it is split off before conversion and its fields
travel as ``doc_*`` chunk metadata instead of being embedded as text.
"""

import re
from collections.abc import Iterator
from typing import Any

import yaml

# A header must close within these limits; otherwise the leading ``---`` is
# treated as ordinary content (e.g. a horizontal rule) and nothing is split.
MAX_HEADER_CHARS = 64 * 1024
MAX_HEADER_LINES = 100

METADATA_PREFIX = "doc_"

# A block is a header only if it names at least one of these, so a document
# that merely opens with ``---`` rules around ``Note: ...`` lines is left alone.
KNOWN_KEYS = frozenset({"title", "url", "source", "author", "published_date"})

_DELIMITER = "---"
_BOM = chr(0xFEFF)
_LINE_RE = re.compile(r"[^\r\n]*(?:\r\n|\n|\r|$)")
_FLAT_LINE_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):(?:[ \t]+(.*?))?[ \t]*$")
_KEY_SANITIZE_RE = re.compile(r"[^a-z0-9_]")


class _NoTimestampLoader(yaml.SafeLoader):
    """SafeLoader that keeps dates as the strings written in the file."""


_NoTimestampLoader.yaml_implicit_resolvers = {
    first: [
        (tag, regexp)
        for tag, regexp in resolvers
        if tag != "tag:yaml.org,2002:timestamp"
    ]
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def _iter_lines(text: str) -> Iterator[tuple[str, bool, int, int]]:
    """Yield ``(line_without_eol, has_eol, start, end)`` for each line."""
    for match in _LINE_RE.finditer(text):
        raw = match.group(0)
        if not raw:
            return
        line = raw.rstrip("\r\n")
        yield line, line != raw, match.start(), match.end()


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _parse_flat(block: str) -> dict[str, Any] | None:
    """Parse ``key: value`` lines; None if any non-empty line is not one."""
    fields: dict[str, Any] = {}
    for line, *_ in _iter_lines(block):
        if not line.strip():
            continue
        match = _FLAT_LINE_RE.match(line)
        if not match:
            return None
        fields[match.group(1)] = _strip_quotes(match.group(2) or "")
    return fields


def _parse_block(block: str) -> dict[str, Any] | None:
    """Parse a header block, or None if it is not a flat key/value header.

    The flat parse decides whether the block is a header at all. YAML, when
    it loads the same block as a mapping with the same keys, then supplies
    typed values (numbers, booleans, ``[a, b]`` lists).
    """
    flat = _parse_flat(block)
    if not flat or not KNOWN_KEYS & {key.lower() for key in flat}:
        return None
    try:
        loaded = yaml.load(block, Loader=_NoTimestampLoader)  # noqa: S506  # nosec B506
    except yaml.YAMLError:
        loaded = None
    if isinstance(loaded, dict) and set(map(str, loaded)) == set(flat):
        return {str(key): value for key, value in loaded.items()}
    return flat


def split_front_matter(text: str) -> tuple[dict[str, Any] | None, str]:
    """Split a leading front matter header from Markdown text.

    The header is recognised only when the text (after an optional BOM)
    starts with a line that is exactly ``---``, a second such line follows
    within ``MAX_HEADER_LINES`` lines and ``MAX_HEADER_CHARS`` characters,
    every non-empty line between them is ``key: value`` with an
    identifier-like key, and at least one key is in ``KNOWN_KEYS``.

    Returns:
        ``(fields, body)`` when a header is found, where ``body`` is the text
        after the closing delimiter line. ``(None, text)`` otherwise, with
        the text unchanged.
    """
    start = 1 if text.startswith(_BOM) else 0
    head = text[start : start + MAX_HEADER_CHARS]

    lines = _iter_lines(head)
    first = next(lines, None)
    if first is None or first[0] != _DELIMITER or not first[1]:
        return None, text
    block_start = first[3]

    for count, (line, has_eol, line_start, end) in enumerate(lines, start=1):
        if count > MAX_HEADER_LINES:
            break
        # A line cut by the size limit is not a complete line.
        complete = has_eol or start + end == len(text)
        if line == _DELIMITER and complete:
            fields = _parse_block(head[block_start:line_start])
            if fields is None:
                return None, text
            return fields, text[start + end :]
    return None, text


def _scalar(value: Any) -> str | int | float | bool | None:
    if isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, list | tuple):
        items = [str(v) for v in value if isinstance(v, str | int | float | bool)]
        return ", ".join(items) if items else None
    return None


def front_matter_metadata(fields: dict[str, Any]) -> dict[str, Any]:
    """Map header fields to ``doc_<key>`` scalar metadata.

    Keys are lowercased with every character outside ``[a-z0-9_]`` replaced
    by ``_``. Scalars pass through, lists of scalars are joined with ``", "``,
    and None, empty lists and nested values are dropped.
    """
    metadata: dict[str, Any] = {}
    for key, value in fields.items():
        name = _KEY_SANITIZE_RE.sub("_", str(key).strip().lower())
        scalar = _scalar(value)
        if not name or scalar is None:
            continue
        metadata[f"{METADATA_PREFIX}{name}"] = scalar
    return metadata
