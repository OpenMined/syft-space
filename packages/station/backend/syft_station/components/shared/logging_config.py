"""Loguru configuration — importing this module configures logging."""

import logging
import sys

from loguru import logger

from syft_station.config import app_settings


class InterceptHandler(logging.Handler):
    """Route stdlib logging records through loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = str(record.levelno)
        logger.opt(depth=6, exception=record.exc_info).log(level, record.getMessage())


logger.remove()
logger.add(sys.stderr, level=app_settings.log_level.upper())
logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
