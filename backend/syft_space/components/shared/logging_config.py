"""Unified logging configuration using loguru.

This module intercepts all standard library logging (used by uvicorn, alembic, etc.)
and routes it through loguru for consistent log formatting.

Import this module early in the application to ensure all logs are captured.
"""

import inspect
import logging
import sys
from pathlib import Path

from loguru import logger

from syft_space.config import app_settings

# Remove loguru's default handler
logger.remove()

# Console handler (stderr)
# colorize=None lets loguru auto-detect TTY (colors in terminals, plain in Docker/pipes)
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <5}</level> | <cyan>{name}</cyan> - <level>{message}</level>",
    level=app_settings.log_level.upper(),
    colorize=None,
)

# File handler
log_path = Path(app_settings.log_file).expanduser()
try:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger.add(
        str(log_path.resolve()),
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <5} | {name} - {message}",
        level=app_settings.log_level.upper(),
        rotation="50 MB",
        retention="7 days",
        compression="gz",
        colorize=False,
    )
except OSError as e:
    # Some environments (e.g. restricted sandboxes) may not allow writing to the
    # default user directory. Keep console logging enabled so the server can run.
    logger.warning(f"File logging disabled (cannot write to {log_path!s}): {e!s}")


class InterceptHandler(logging.Handler):
    """Handler that intercepts standard logging and routes to loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where the logged message originated
        frame = inspect.currentframe()
        depth = 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging() -> None:
    """Configure all logging to route through loguru."""
    # Install intercept handler for all standard library logging
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Specifically configure uvicorn and alembic loggers
    for logger_name in (
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "alembic",
        "alembic.runtime.migration",
        "sqlalchemy",
    ):
        logging.getLogger(logger_name).handlers = [InterceptHandler()]
        logging.getLogger(logger_name).propagate = False


# Auto-setup on import
setup_logging()
