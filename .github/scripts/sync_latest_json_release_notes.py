#!/usr/bin/env python3
"""Copy published GitHub release notes into Tauri's generated latest.json."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def run_gh_release_view(tag: str) -> dict[str, Any]:
    result = subprocess.run(
        [
            "gh",
            "release",
            "view",
            tag,
            "--json",
            "body,createdAt,publishedAt,tagName",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise SystemExit(result.returncode)

    return json.loads(result.stdout)


def sync_notes(latest_json_path: Path, release_info: dict[str, Any]) -> dict[str, Any]:
    with latest_json_path.open() as latest_json_file:
        latest_json = json.load(latest_json_file)

    latest_json["notes"] = release_info.get("body") or ""
    latest_json["pub_date"] = (
        release_info.get("publishedAt")
        or release_info.get("createdAt")
        or latest_json.get("pub_date")
    )

    return latest_json


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Update latest.json notes from a published GitHub release body."
    )
    parser.add_argument("tag", help="GitHub release tag to read")
    parser.add_argument(
        "--latest-json",
        default="latest.json",
        type=Path,
        help="Path to the generated latest.json file",
    )
    parser.add_argument(
        "--output",
        default="latest.json",
        type=Path,
        help="Where to write the updated latest.json file",
    )
    args = parser.parse_args()

    release_info = run_gh_release_view(args.tag)
    latest_json = sync_notes(args.latest_json, release_info)

    with args.output.open("w") as output_file:
        json.dump(latest_json, output_file, indent=2)
        output_file.write("\n")


if __name__ == "__main__":
    main()
