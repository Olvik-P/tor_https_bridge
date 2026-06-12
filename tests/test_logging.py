"""Tests for tor_https_bridge.utils.logging."""

from __future__ import annotations

import io
import logging

import pytest

from tor_https_bridge.utils.logging import get_logger, setup_logging


class TestSetupLogging:
    """Tests for setup_logging."""

    @pytest.fixture(autouse=True)
    def _reset_logging(self) -> None:
        """Reset root logger handlers before each test."""
        root = logging.getLogger()
        for handler in list(root.handlers):
            root.removeHandler(handler)
        root.setLevel(logging.WARNING)

    def test_setup_logging_default_level(self) -> None:
        stream = io.StringIO()
        setup_logging(stream=stream)

        root = logging.getLogger()
        assert root.level == logging.INFO

        logger = logging.getLogger("test")
        logger.info("test message")
        output = stream.getvalue()
        assert "test message" in output

    def test_setup_logging_debug_level(self) -> None:
        stream = io.StringIO()
        setup_logging(level="DEBUG", stream=stream)

        root = logging.getLogger()
        assert root.level == logging.DEBUG

        logger = logging.getLogger("test")
        logger.debug("debug message")
        output = stream.getvalue()
        assert "debug message" in output

    def test_setup_logging_warning_level(self) -> None:
        stream = io.StringIO()
        setup_logging(level="WARNING", stream=stream)

        root = logging.getLogger()
        assert root.level == logging.WARNING

        logger = logging.getLogger("test")
        logger.info("info message")
        logger.warning("warning message")
        output = stream.getvalue()
        assert "info message" not in output
        assert "warning message" in output

    def test_setup_logging_with_int_level(self) -> None:
        stream = io.StringIO()
        setup_logging(level=logging.ERROR, stream=stream)

        root = logging.getLogger()
        assert root.level == logging.ERROR

    def test_setup_logging_format(self) -> None:
        stream = io.StringIO()
        setup_logging(level="INFO", stream=stream)

        logger = logging.getLogger("test")
        logger.info("format test")
        output = stream.getvalue()

        # Should contain timestamp, level, and message
        assert "INFO" in output
        assert "format test" in output

    def test_setup_logging_silences_asyncio(self) -> None:
        stream = io.StringIO()
        setup_logging(level="DEBUG", stream=stream)

        asyncio_logger = logging.getLogger("asyncio")
        assert asyncio_logger.level == logging.WARNING

    def test_setup_logging_silences_pydantic(self) -> None:
        stream = io.StringIO()
        setup_logging(level="DEBUG", stream=stream)

        pydantic_logger = logging.getLogger("pydantic")
        assert pydantic_logger.level == logging.WARNING

    def test_setup_logging_invalid_level_defaults_to_info(self) -> None:
        stream = io.StringIO()
        setup_logging(level="INVALID", stream=stream)

        root = logging.getLogger()
        assert root.level == logging.INFO


class TestGetLogger:
    """Tests for get_logger."""

    def test_get_logger_returns_logger(self) -> None:
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_module"

    def test_get_logger_with_dunder_name(self) -> None:
        logger = get_logger(__name__)
        assert logger.name == __name__

    def test_get_logger_reuses_existing(self) -> None:
        logger1 = get_logger("shared")
        logger2 = get_logger("shared")
        assert logger1 is logger2
