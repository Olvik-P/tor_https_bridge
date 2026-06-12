"""Structured logging configuration for Tor HTTPS Bridge Proxy."""

from __future__ import annotations

import logging
import sys
from typing import TextIO

from tor_https_bridge.config.constants import LOG_DATE_FORMAT, LOG_FORMAT


def setup_logging(
    level: str | int = logging.INFO,
    stream: TextIO = sys.stderr,
) -> None:
    """Configure structured logging with consistent formatting.

    Sets up a root logger with a stream handler and a standardised
    format. Silences noisy third-party loggers (e.g. ``asyncio``).

    Usage::

        from tor_https_bridge.utils.logging import setup_logging
        setup_logging(level='DEBUG')

    Args:
        level: Logging level — name (``'INFO'``) or constant
            (``logging.DEBUG``).
        stream: Output stream (default: ``sys.stderr``).
    """
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    handler = logging.StreamHandler(stream)
    handler.setFormatter(
        logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT),
    )

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)

    # Silence noisy libraries
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("pydantic").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given *name*.

    Args:
        name: Logger name (typically ``__name__``).

    Returns:
        Configured logger instance.
    """
    return logging.getLogger(name)
