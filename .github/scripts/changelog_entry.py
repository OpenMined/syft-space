"""Add one release entry to a package's changelog.

The entry's body, the list of changes, is built by the release workflow and
passed in as a file. This script gives it a heading with today's date and
puts it at the top of the changelog.

    python .github/scripts/changelog_entry.py packages/station/CHANGELOG.md \
        "0.2.4" --body body.md
"""

from __future__ import annotations

import argparse
import datetime
import re
from pathlib import Path

BULLET_START = re.compile(r"^- ([a-z])", flags=re.MULTILINE)


def has_entry(changelog: str, heading: str) -> bool:
    """Whether a release with this heading is already listed."""
    pattern = rf"^## {re.escape(heading)} \("
    return re.search(pattern, changelog, flags=re.MULTILINE) is not None


def entry(heading: str, date: str, body: str) -> str:
    """The Markdown for one release: a heading, then the body tidied."""
    # Each line starts with a capital, and one blank line follows a heading.
    body = BULLET_START.sub(lambda match: f"- {match.group(1).upper()}", body.strip())
    body = re.sub(r"\n{3,}", "\n\n", body)
    body = re.sub(r"^(### .+)\n(?!\n)", r"\1\n\n", body, flags=re.MULTILINE)
    return f"## {heading} ({date})\n\n{body or 'No user-facing changes.'}\n"


def insert(changelog: str, new_entry: str) -> str:
    """Put the entry above the newest one, below the file's introduction."""
    first = re.search(r"^## ", changelog, flags=re.MULTILINE)
    if first is None:
        return changelog.rstrip("\n") + "\n\n" + new_entry
    return changelog[: first.start()] + new_entry + "\n" + changelog[first.start() :]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("changelog", help="the package's CHANGELOG.md")
    parser.add_argument("heading", help='what is released, e.g. "0.2.4"')
    parser.add_argument("--body", required=True, help="file with the list of changes")
    parser.add_argument("--dry-run", action="store_true", help="print, do not write")
    args = parser.parse_args()

    path = Path(args.changelog)
    changelog = path.read_text()
    if has_entry(changelog, args.heading):
        print(f"{args.heading} already has an entry; nothing to do.")
        return

    date = datetime.datetime.now(datetime.UTC).date().isoformat()
    new_entry = entry(args.heading, date, Path(args.body).read_text())
    if args.dry_run:
        print(new_entry)
        return
    path.write_text(insert(changelog, new_entry))


if __name__ == "__main__":
    main()
