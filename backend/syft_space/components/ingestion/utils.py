from collections.abc import Generator
from pathlib import Path

GLOB_PATTERN = "*"


def rglob_visible(
    path: Path, pattern: str = GLOB_PATTERN
) -> Generator[Path, None, None]:
    """Like rglob but ignores hidden files and directories."""
    for file_path in path.rglob(pattern):
        if not any(part.startswith(".") for part in file_path.parts):
            yield file_path
