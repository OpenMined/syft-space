"""Add one release entry to the Syft Space image changelog.

An image is named by its tag, the short commit id it was built from. The
entry's body, the list of changes, is built by the publish workflow and
passed in as a file. This script gives it a heading and puts it at the top
of the changelog.

    python .github/scripts/space_changelog.py a39dda6 --body body.md
"""

from __future__ import annotations

import argparse
import datetime
import re
from pathlib import Path

CHANGELOG = Path("packages/spaces/CHANGELOG.md")
HEADING = re.compile(r"^## Docker image (?P<image>\S+) \(", flags=re.MULTILINE)
BULLET_START = re.compile(r"^- ([a-z])", flags=re.MULTILINE)


def listed_images(changelog: str) -> list[str]:
    """Image tags that already have an entry, newest first."""
    return [match.group("image") for match in HEADING.finditer(changelog)]


def entry(image: str, date: str, body: str) -> str:
    """The Markdown for one release: a heading, then the body tidied."""
    # Each line starts with a capital, and one blank line follows a heading.
    body = BULLET_START.sub(lambda match: f"- {match.group(1).upper()}", body.strip())
    body = re.sub(r"\n{3,}", "\n\n", body)
    body = re.sub(r"^(### .+)\n(?!\n)", r"\1\n\n", body, flags=re.MULTILINE)
    return f"## Docker image {image} ({date})\n\n{body or 'No user-facing changes.'}\n"


def insert(changelog: str, new_entry: str) -> str:
    """Put the entry above the newest one, below the file's introduction."""
    first = re.search(r"^## ", changelog, flags=re.MULTILINE)
    if first is None:
        return changelog.rstrip("\n") + "\n\n" + new_entry
    return changelog[: first.start()] + new_entry + "\n" + changelog[first.start() :]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("image", help="tag of the image: its short commit id")
    parser.add_argument("--body", required=True, help="file with the list of changes")
    parser.add_argument("--dry-run", action="store_true", help="print, do not write")
    args = parser.parse_args()

    changelog = CHANGELOG.read_text()
    if args.image in listed_images(changelog):
        print(f"{args.image} already has an entry; nothing to do.")
        return

    date = datetime.datetime.now(datetime.UTC).date().isoformat()
    new_entry = entry(args.image, date, Path(args.body).read_text())
    if args.dry_run:
        print(new_entry)
        return
    CHANGELOG.write_text(insert(changelog, new_entry))


if __name__ == "__main__":
    main()
