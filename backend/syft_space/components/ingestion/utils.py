from collections.abc import AsyncGenerator

from anyio import Path as AsyncPath

GLOB_PATTERN = "*"


async def rglob_visible(
    path: AsyncPath, pattern: str = GLOB_PATTERN
) -> AsyncGenerator[AsyncPath, None]:
    """Like rglob but ignores hidden files and directories."""
    async for file_path in path.rglob(pattern):
        if not any(part.startswith(".") for part in file_path.parts):
            yield file_path
