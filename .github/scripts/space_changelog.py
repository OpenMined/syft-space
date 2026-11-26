"""Add one release entry to the Syft Space image changelog.

An image is named by its tag, the short commit id it was built from. The
entry lists the pull requests merged between the previous image's commit and
this one that touch the image's code, grouped by the type in their title.

The previous image's commit is passed in by the publish workflow, which reads
it from the registry. Without it, the newest entry in the changelog is used.

    python .github/scripts/space_changelog.py a39dda6 --since 58c6376b
"""

from __future__ import annotations

import argparse
import datetime
import re
import subprocess
from pathlib import Path

CHANGELOG = Path("packages/spaces/CHANGELOG.md")
# What the image is built from; the desktop shell is not part of it.
IMAGE_PATHS = ("packages/spaces", ":!packages/spaces/src-tauri")
HEADING = re.compile(r"^## Docker image (?P<image>\S+) \(", flags=re.MULTILINE)

# Title type -> section. Types not listed here are left out of the entry.
SECTIONS = {
    "feat": "Added",
    "fix": "Fixed",
    "perf": "Changed",
    "refactor": "Changed",
    "revert": "Changed",
}
SECTION_ORDER = ("Added", "Changed", "Fixed")
TITLE = re.compile(r"^(?P<type>[a-z]+)(\([^)]*\))?!?:\s*(?P<subject>.+)$")
PR_NUMBER = re.compile(r"#(\d+)")


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def commit(ref: str) -> str | None:
    """The full id of the commit `ref` names, or None if this clone lacks it."""
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() or None


def start_of_changes(image: str, given: str | None, listed: list[str]) -> str | None:
    """The commit to count changes from: `given`, else the newest entry's."""
    for candidate in (given, listed[0] if listed else None):
        # A re-run finds this image already published; that is not a start.
        if candidate and commit(candidate) not in (None, commit(image)):
            return candidate
    return None


def listed_images(changelog: str) -> list[str]:
    """Image tags that already have an entry, newest first."""
    return [match.group("image") for match in HEADING.finditer(changelog)]


def merged_pull_requests(since: str, until: str) -> list[int]:
    """Numbers of the PRs merged after `since` up to `until`, oldest first."""
    subjects = git(
        "log", "--first-parent", "--reverse", "--format=%s", f"{since}..{until}",
        "--", *IMAGE_PATHS,
    )  # fmt: skip
    numbers: list[int] = []
    for subject in subjects.splitlines():
        match = PR_NUMBER.search(subject)
        if match and int(match.group(1)) not in numbers:
            numbers.append(int(match.group(1)))
    return numbers


def pull_request_title(number: int) -> str | None:
    result = subprocess.run(
        ["gh", "pr", "view", str(number), "--json", "title", "--jq", ".title"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() or None


def entry(image: str, date: str, titles: dict[int, str]) -> str:
    """The Markdown for one release."""
    sections: dict[str, list[str]] = {name: [] for name in SECTION_ORDER}
    for number, title in titles.items():
        match = TITLE.match(title)
        if not match or match.group("type") not in SECTIONS:
            continue
        subject = match.group("subject")
        line = f"- {subject[0].upper()}{subject[1:]} (#{number})"
        sections[SECTIONS[match.group("type")]].append(line)

    lines = [f"## Docker image {image} ({date})", ""]
    for name in SECTION_ORDER:
        if sections[name]:
            lines += [f"### {name}", "", *sections[name], ""]
    if len(lines) == 2:
        lines += ["No user-facing changes.", ""]
    return "\n".join(lines)


def insert(changelog: str, new_entry: str) -> str:
    """Put the entry above the newest one, below the file's introduction."""
    first = re.search(r"^## ", changelog, flags=re.MULTILINE)
    if first is None:
        return changelog.rstrip("\n") + "\n\n" + new_entry
    return changelog[: first.start()] + new_entry + "\n" + changelog[first.start() :]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("image", help="tag of the image: its short commit id")
    parser.add_argument("--since", help="commit the previous image was built from")
    parser.add_argument("--dry-run", action="store_true", help="print, do not write")
    args = parser.parse_args()

    changelog = CHANGELOG.read_text()
    listed = listed_images(changelog)
    if args.image in listed:
        print(f"{args.image} already has an entry; nothing to do.")
        return

    since = start_of_changes(args.image, args.since, listed)
    date = datetime.datetime.now(datetime.UTC).date().isoformat()
    if since is None:
        new_entry = f"## Docker image {args.image} ({date})\n\n"
        new_entry += "No earlier image to compare with.\n"
    else:
        titles: dict[int, str] = {}
        for number in merged_pull_requests(since, args.image):
            title = pull_request_title(number)
            if title:
                titles[number] = title
        new_entry = entry(args.image, date, titles)

    if args.dry_run:
        print(new_entry)
        return
    CHANGELOG.write_text(insert(changelog, new_entry))


if __name__ == "__main__":
    main()
