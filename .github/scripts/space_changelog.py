"""Add one release entry to the Syft Space image changelog.

An image is named by its tag, the short commit id it was built from. The
entry lists the pull requests merged between the previous image's commit and
this one that touch the image's code, grouped by the type in their title.
A pull request is breaking if its title has `!` before the colon, or its
description has a line starting with `BREAKING CHANGE:`.

The previous image's commit is passed in by the publish workflow, which reads
it from the registry. Without it, the newest entry in the changelog is used.

    python .github/scripts/space_changelog.py a39dda6 --since 58c6376b

A model may reword the lines. `--facts` writes what it is given, and
`--wording` reads its answer, one `#<number>: <sentence>` per pull request.
An answer that is not exactly that is ignored, and the titles are used.
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

# What a model's line may be: one plain sentence, no Markdown or links.
WORDING_LINE = re.compile(r"^#(?P<number>\d+):\s*(?P<sentence>.+)$")
WORDING_MAX_CHARS = 200
WORDING_FORBIDDEN = re.compile(r"[\[\]<>`*|]|https?://|#\d")
# How much of each pull request the model is shown.
FACTS_BODY_CHARS = 1500
FACTS_MAX_FILES = 30


@dataclass
class PullRequest:
    number: int
    title: str
    body: str
    files: list[str]


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
        ["gh", "pr", "view", str(number), "--json", "title,body,files"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    data = json.loads(result.stdout)
    files = [f["path"] for f in data.get("files") or [] if in_image(f["path"])]
    return PullRequest(number, data["title"].strip(), data.get("body") or "", files)


def in_image(path: str) -> bool:
    return path.startswith("packages/spaces/") and not path.startswith(
        "packages/spaces/src-tauri/"
    )


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


def listed(pull_requests: list[PullRequest]) -> list[PullRequest]:
    """The pull requests that get a line in the entry."""
    return [pr for pr in pull_requests if section_and_subject(pr)[0] is not None]


def facts(pull_requests: list[PullRequest]) -> str:
    """What a model is given to reword: the listed pull requests, as text."""
    blocks = []
    for pr in listed(pull_requests):
        section, _ = section_and_subject(pr)
        files = pr.files[:FACTS_MAX_FILES]
        more = len(pr.files) - len(files)
        blocks.append(
            "\n".join(
                [
                    f"Pull request #{pr.number}",
                    f"Group: {section}",
                    f"Title: {pr.title}",
                    "Files changed in the Syft Space image:",
                    *(f"  {path}" for path in files),
                    *([f"  and {more} more"] if more > 0 else []),
                    "Description:",
                    pr.body.strip()[:FACTS_BODY_CHARS] or "(none)",
                ]
            )
        )
    return "\n\n---\n\n".join(blocks) + "\n" if blocks else ""


def read_wording(text: str, pull_requests: list[PullRequest]) -> dict[int, str] | None:
    """A model's sentences by PR number, or None unless the answer is exact.

    Exact means one valid line for each listed pull request and nothing else,
    so a model can phrase a change but cannot add, drop or link one.
    """
    wording: dict[int, str] = {}
    for line in text.strip().splitlines():
        match = WORDING_LINE.match(line.strip())
        if match is None:
            return None
        sentence = match["sentence"].strip().rstrip(".")
        number = int(match["number"])
        if number in wording or not sentence or len(sentence) > WORDING_MAX_CHARS:
            return None
        if WORDING_FORBIDDEN.search(sentence):
            return None
        wording[number] = sentence
    if set(wording) != {pr.number for pr in listed(pull_requests)}:
        return None
    return wording


def entry(
    image: str,
    date: str,
    pull_requests: list[PullRequest],
    wording: dict[int, str] | None = None,
) -> str:
    """The Markdown for one release; `wording` replaces the titles' subjects."""
    sections: dict[str, list[str]] = {name: [] for name in SECTION_ORDER}
    for pr in listed(pull_requests):
        section, subject = section_and_subject(pr)
        text = (wording or {}).get(pr.number, subject)
        link = f"[#{pr.number}](https://github.com/{REPOSITORY}/pull/{pr.number})"
        sections[section or OTHER].append(f"- {text[0].upper()}{text[1:]} ({link})")

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
    parser.add_argument("--facts", help="write the model's input here, and stop")
    parser.add_argument("--wording", help="file holding the model's answer")
    parser.add_argument("--dry-run", action="store_true", help="print, do not write")
    args = parser.parse_args()

    changelog = CHANGELOG.read_text()
    images = listed_images(changelog)
    if args.image in images:
        print(f"{args.image} already has an entry; nothing to do.")
        return

    since = start_of_changes(args.image, args.since, images)
    found = merged_pull_requests(since, args.image) if since else []
    pull_requests = [pr for pr in map(pull_request, found) if pr]

    if args.facts:
        Path(args.facts).write_text(facts(pull_requests))
        return

    wording = None
    if args.wording and Path(args.wording).is_file():
        wording = read_wording(Path(args.wording).read_text(), pull_requests)
        print("Using the model's wording." if wording else "Using the PR titles.")

    date = datetime.datetime.now(datetime.UTC).date().isoformat()
    if since is None:
        new_entry = f"## Docker image {args.image} ({date})\n\n"
        new_entry += "No earlier image to compare with.\n"
    else:
        new_entry = entry(args.image, date, pull_requests, wording)

    if args.dry_run:
        print(new_entry)
        return
    CHANGELOG.write_text(insert(changelog, new_entry))


if __name__ == "__main__":
    main()
