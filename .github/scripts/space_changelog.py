"""Add one release entry to the Syft Space image changelog.

An image is named by its tag, the short commit id it was built from. The
entry lists the pull requests merged between the previous image's commit and
this one that touch the image's code, grouped by the type in their title.
A pull request is breaking if its title has `!` before the colon, or its
description has a line starting with `BREAKING CHANGE:`.

The previous image's commit is passed in by the publish workflow, which reads
it from the registry. Without it, the newest entry in the changelog is used.

    python .github/scripts/space_changelog.py a39dda6 --since 58c6376b
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

CHANGELOG = Path("packages/spaces/CHANGELOG.md")
# What the image is built from; the desktop shell is not part of it.
IMAGE_PATHS = ("packages/spaces", ":!packages/spaces/src-tauri")
HEADING = re.compile(r"^## Docker image (?P<image>\S+) \(", flags=re.MULTILINE)

REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "OpenMined/syft-space")

# Title type -> section. A title with no known type goes under Other.
SECTIONS = {
    "feat": "Added",
    "fix": "Fixed",
    "perf": "Changed",
    "refactor": "Changed",
    "revert": "Changed",
}
# Housekeeping: left out of the entry unless marked breaking.
SKIPPED_TYPES = {"chore", "docs", "test", "ci", "style", "build"}
BREAKING = "Breaking"
OTHER = "Other"
SECTION_ORDER = (BREAKING, "Added", "Changed", "Fixed", OTHER)

TITLE = re.compile(r"^(?P<type>[a-z]+)(\([^)]*\))?(?P<bang>!)?:\s*(?P<subject>.+)$")
BREAKING_FOOTER = re.compile(r"^BREAKING[ -]CHANGE:", flags=re.MULTILINE)
PR_NUMBER = re.compile(r"#(\d+)")


@dataclass
class PullRequest:
    number: int
    title: str
    body: str


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


def pull_request(number: int) -> PullRequest | None:
    result = subprocess.run(
        ["gh", "pr", "view", str(number), "--json", "title,body"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    data = json.loads(result.stdout)
    return PullRequest(number, data["title"].strip(), data.get("body") or "")


def section_and_subject(pr: PullRequest) -> tuple[str | None, str]:
    """Where a pull request is listed (None: not listed) and its wording."""
    match = TITLE.match(pr.title)
    if match is None:
        subject, kind, bang = pr.title, None, False
    else:
        subject, kind, bang = match["subject"], match["type"], bool(match["bang"])

    if bang or BREAKING_FOOTER.search(pr.body):
        return BREAKING, subject
    if kind in SKIPPED_TYPES:
        return None, subject
    return SECTIONS.get(kind or "", OTHER), subject


def entry(image: str, date: str, pull_requests: list[PullRequest]) -> str:
    """The Markdown for one release."""
    sections: dict[str, list[str]] = {name: [] for name in SECTION_ORDER}
    for pr in pull_requests:
        section, subject = section_and_subject(pr)
        if section is None:
            continue
        link = f"[#{pr.number}](https://github.com/{REPOSITORY}/pull/{pr.number})"
        sections[section].append(f"- {subject[0].upper()}{subject[1:]} ({link})")

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
        found = [pull_request(n) for n in merged_pull_requests(since, args.image)]
        new_entry = entry(args.image, date, [pr for pr in found if pr])

    if args.dry_run:
        print(new_entry)
        return
    CHANGELOG.write_text(insert(changelog, new_entry))


if __name__ == "__main__":
    main()
