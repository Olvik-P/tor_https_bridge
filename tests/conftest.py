"""Shared fixtures and configuration for tests."""

from __future__ import annotations

import asyncio
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from tor_https_bridge.config.settings import Settings
from tor_https_bridge.core.forwarder import DataForwarder
from tor_https_bridge.core.handler import ClientHandler
from tor_https_bridge.protocol.http_parser import HTTPConnectParser
from tor_https_bridge.protocol.socks_adapter import TorConnector

# ============================================================================
# Settings fixtures
# ============================================================================


@pytest.fixture
def settings() -> Settings:
    """Return default application settings."""
    return Settings(
        sanitize_headers=False,
    )


@pytest.fixture
def custom_settings() -> Settings:
    """Return custom application settings for testing."""
    return Settings(
        tor_socks_host="127.0.0.1",
        tor_socks_port=9050,
        https_proxy_host="127.0.0.1",
        https_proxy_port=3128,
        buffer_size=4096,
        backlog=10,
        connect_timeout=5,
        read_timeout=10,
        log_level="DEBUG",
        sanitize_headers=False,
    )


# ============================================================================
# Mock fixtures
# ============================================================================


@pytest.fixture
def mock_reader() -> AsyncMock:
    """Return a mock asyncio.StreamReader."""
    reader = AsyncMock(spec=asyncio.StreamReader)
    reader.read = AsyncMock(return_value=b"")
    reader.at_eof = MagicMock(return_value=True)
    return reader


@pytest.fixture
def mock_writer() -> AsyncMock:
    """Return a mock asyncio.StreamWriter."""
    writer = AsyncMock(spec=asyncio.StreamWriter)
    writer.drain = AsyncMock()
    writer.wait_closed = AsyncMock()
    writer.close = MagicMock()
    writer.is_closing = MagicMock(return_value=False)
    writer.get_extra_info = MagicMock(return_value=("127.0.0.1", 54321))
    return writer


@pytest.fixture
def mock_parser() -> MagicMock:
    """Return a mock HTTPConnectParser."""
    parser = MagicMock(spec=HTTPConnectParser)
    parser.read_request = AsyncMock(
        return_value=b"CONNECT example.com:443 HTTP/1.1\r\n\r\n"
    )
    parser.parse_connect = MagicMock(
        return_value=("example.com", 443, "CONNECT")
    )
    return parser


@pytest.fixture
def mock_connector() -> AsyncMock:
    """Return a mock TorConnector."""
    connector = AsyncMock(spec=TorConnector)

    @pytest_asyncio.fixture
    async def _mock_connect(host: str, port: int) -> AsyncIterator[MagicMock]:
        mock_sock = MagicMock()
        mock_sock.fileno = MagicMock(return_value=3)
        mock_sock.close = MagicMock()
        yield mock_sock

    connector.connect = AsyncMock()
    # Make connect work as async context manager
    cm = connector.connect.return_value
    cm.__aenter__ = AsyncMock(return_value=MagicMock())
    cm.__aexit__ = AsyncMock(return_value=None)

    return connector


@pytest.fixture
def mock_forwarder() -> AsyncMock:
    """Return a mock DataForwarder."""
    forwarder = AsyncMock(spec=DataForwarder)
    forwarder.forward_bidirectional = AsyncMock()
    forwarder.forward_one_way = AsyncMock()
    return forwarder


@pytest.fixture
def handler(
    settings: Settings,
    mock_parser: MagicMock,
    mock_connector: AsyncMock,
    mock_forwarder: AsyncMock,
) -> ClientHandler:
    """Return a ClientHandler with mocked dependencies."""
    return ClientHandler(
        settings=settings,
        parser=mock_parser,
        connector=mock_connector,
        forwarder=mock_forwarder,
    )


# ============================================================================
# Async fixtures
# ============================================================================


@pytest.fixture
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()
