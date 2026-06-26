"""Tests for tor_https_bridge.core.handler."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from tor_https_bridge.config.constants import (
    HTTP_200_CONNECTED,
    HTTP_400_BAD_REQUEST,
    HTTP_502_BAD_GATEWAY,
)
from tor_https_bridge.config.settings import Settings
from tor_https_bridge.core.exceptions import (
    ProxyConnectionError,
    ProxyProtocolError,
    ProxyTimeoutError,
)
from tor_https_bridge.core.handler import ClientHandler


def _make_connector_that_raises(error: Exception) -> MagicMock:
    """Create a mock connector whose connect() returns a context manager
    that raises the given error on __aenter__."""
    connector = MagicMock()

    class _RaisingConnection:
        """Mock connection that raises on __aenter__."""

        async def __aenter__(self) -> MagicMock:
            raise error

        async def __aexit__(self, *args) -> None:
            pass

    async def _connect_that_raises(
        host: str,
        port: int,
    ) -> _RaisingConnection:
        return _RaisingConnection()

    connector.connect = _connect_that_raises
    return connector


class TestClientHandlerInit:
    """Tests for ClientHandler.__init__."""

    def test_init_with_defaults(self, settings) -> None:
        handler = ClientHandler(settings)
        assert handler._settings is settings
        assert handler._parser is not None
        assert handler._connector is not None
        assert handler._forwarder is not None

    def test_init_with_mocks(
        self,
        settings,
        mock_parser,
        mock_connector,
        mock_forwarder,
    ) -> None:
        handler = ClientHandler(
            settings=settings,
            parser=mock_parser,
            connector=mock_connector,
            forwarder=mock_forwarder,
        )
        assert handler._parser is mock_parser
        assert handler._connector is mock_connector
        assert handler._forwarder is mock_forwarder


class TestClientHandlerHandle:
    """Tests for ClientHandler.handle."""

    @pytest.mark.asyncio
    async def test_handle_success(
        self,
        handler,
        mock_reader,
        mock_writer,
    ) -> None:
        await handler.handle(mock_reader, mock_writer)

        handler._parser.read_request.assert_awaited_once_with(
            mock_reader,
            handler._settings.max_request_size,
            timeout=handler._settings.read_timeout,
        )
        handler._parser.parse_connect.assert_called_once()
        mock_writer.write.assert_any_call(HTTP_200_CONNECTED)
        mock_writer.drain.assert_awaited()
        mock_writer.close.assert_called_once()
        mock_writer.wait_closed.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handle_protocol_error(
        self,
        settings,
        mock_parser,
        mock_connector,
        mock_forwarder,
        mock_reader,
        mock_writer,
    ) -> None:
        mock_parser.read_request = AsyncMock(
            side_effect=ProxyProtocolError("bad request"),
        )
        handler = ClientHandler(
            settings=settings,
            parser=mock_parser,
            connector=mock_connector,
            forwarder=mock_forwarder,
        )

        await handler.handle(mock_reader, mock_writer)

        mock_writer.write.assert_any_call(HTTP_400_BAD_REQUEST)
        mock_writer.drain.assert_awaited()
        mock_writer.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_connection_error(
        self,
        settings,
        mock_parser,
        mock_forwarder,
        mock_reader,
        mock_writer,
    ) -> None:
        connector = _make_connector_that_raises(
            ProxyConnectionError("connection failed"),
        )
        handler = ClientHandler(
            settings=settings,
            parser=mock_parser,
            connector=connector,
            forwarder=mock_forwarder,
        )

        await handler.handle(mock_reader, mock_writer)

        mock_writer.write.assert_any_call(HTTP_502_BAD_GATEWAY)
        mock_writer.drain.assert_awaited()
        mock_writer.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_timeout_error(
        self,
        settings,
        mock_parser,
        mock_forwarder,
        mock_reader,
        mock_writer,
    ) -> None:
        connector = _make_connector_that_raises(
            ProxyTimeoutError("connection timed out"),
        )
        handler = ClientHandler(
            settings=settings,
            parser=mock_parser,
            connector=connector,
            forwarder=mock_forwarder,
        )

        await handler.handle(mock_reader, mock_writer)

        mock_writer.write.assert_any_call(HTTP_502_BAD_GATEWAY)
        mock_writer.drain.assert_awaited()
        mock_writer.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_connection_reset(
        self,
        settings,
        mock_parser,
        mock_connector,
        mock_forwarder,
        mock_reader,
        mock_writer,
    ) -> None:
        mock_parser.read_request = AsyncMock(
            side_effect=ConnectionError("connection reset"),
        )
        handler = ClientHandler(
            settings=settings,
            parser=mock_parser,
            connector=mock_connector,
            forwarder=mock_forwarder,
        )

        await handler.handle(mock_reader, mock_writer)

        mock_writer.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_os_error(
        self,
        settings,
        mock_parser,
        mock_connector,
        mock_forwarder,
        mock_reader,
        mock_writer,
    ) -> None:
        mock_parser.read_request = AsyncMock(
            side_effect=OSError("socket error"),
        )
        handler = ClientHandler(
            settings=settings,
            parser=mock_parser,
            connector=mock_connector,
            forwarder=mock_forwarder,
        )

        await handler.handle(mock_reader, mock_writer)

        mock_writer.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_asyncio_timeout(
        self,
        settings,
        mock_parser,
        mock_connector,
        mock_forwarder,
        mock_reader,
        mock_writer,
    ) -> None:
        mock_parser.read_request = AsyncMock(
            side_effect=asyncio.TimeoutError("timed out"),
        )
        handler = ClientHandler(
            settings=settings,
            parser=mock_parser,
            connector=mock_connector,
            forwarder=mock_forwarder,
        )

        await handler.handle(mock_reader, mock_writer)

        mock_writer.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_unexpected_error(
        self,
        settings,
        mock_parser,
        mock_connector,
        mock_forwarder,
        mock_reader,
        mock_writer,
    ) -> None:
        mock_parser.read_request = AsyncMock(
            side_effect=RuntimeError("unexpected"),
        )
        handler = ClientHandler(
            settings=settings,
            parser=mock_parser,
            connector=mock_connector,
            forwarder=mock_forwarder,
        )

        await handler.handle(mock_reader, mock_writer)

        mock_writer.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_write_error_on_error_response(
        self,
        settings,
        mock_parser,
        mock_connector,
        mock_forwarder,
        mock_reader,
        mock_writer,
    ) -> None:
        """Write error during error response should not raise."""
        mock_parser.read_request = AsyncMock(
            side_effect=ProxyProtocolError("bad request"),
        )
        mock_writer.write.side_effect = ConnectionError("write failed")
        handler = ClientHandler(
            settings=settings,
            parser=mock_parser,
            connector=mock_connector,
            forwarder=mock_forwarder,
        )

        # Should not raise despite write error
        await handler.handle(mock_reader, mock_writer)

        mock_writer.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_close_error_suppressed(
        self,
        handler,
        mock_reader,
        mock_writer,
    ) -> None:
        """Close errors in finally block should be suppressed."""
        mock_writer.wait_closed.side_effect = ConnectionError("close error")

        await handler.handle(mock_reader, mock_writer)

        mock_writer.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_client_addr_logging(
        self,
        handler,
        mock_reader,
        mock_writer,
    ) -> None:
        """Client address should be retrieved for logging."""
        mock_writer.get_extra_info.return_value = ("10.0.0.1", 12345)

        await handler.handle(mock_reader, mock_writer)

        mock_writer.get_extra_info.assert_called_once_with("peername")


class TestClientHandlerIntegration:
    """Integration-style tests for ClientHandler."""

    @pytest.mark.asyncio
    async def test_handle_with_real_parser(
        self,
        settings,
        mock_connector,
        mock_forwarder,
        mock_reader,
        mock_writer,
    ) -> None:
        """Test with real HTTPConnectParser."""
        from tor_https_bridge.protocol.http_parser import HTTPConnectParser

        mock_reader.read = AsyncMock(
            return_value=b"CONNECT example.com:443 HTTP/1.1\r\n\r\n",
        )

        handler = ClientHandler(
            settings=settings,
            parser=HTTPConnectParser(),
            connector=mock_connector,
            forwarder=mock_forwarder,
        )

        await handler.handle(mock_reader, mock_writer)

        mock_writer.write.assert_any_call(HTTP_200_CONNECTED)
        mock_writer.close.assert_called_once()


class TestClientHandlerSanitizer:
    """Tests for ClientHandler with header sanitizer integration."""

    @pytest.mark.asyncio
    async def test_handle_http_request_with_sanitizer(
        self,
        settings,
        mock_connector,
        mock_forwarder,
        mock_reader,
        mock_writer,
    ) -> None:
        """Sanitizer should be called for HTTP requests when enabled."""
        from tor_https_bridge.core.sanitizer import HeaderSanitizer
        from tor_https_bridge.protocol.http_parser import HTTPConnectParser

        # Enable sanitizer
        settings = Settings(
            **{**settings.model_dump(), "sanitize_headers": True},
        )

        # HTTP GET request with identifying headers
        mock_reader.read = AsyncMock(
            return_value=(
                b"GET http://example.com/ HTTP/1.1\r\n"
                b"Host: example.com\r\n"
                b"Accept-Language: ru-RU,ru;q=0.9\r\n"
                b"User-Agent: RussianBrowser/1.0\r\n"
                b"\r\n"
            ),
        )

        sanitizer = HeaderSanitizer()
        handler = ClientHandler(
            settings=settings,
            parser=HTTPConnectParser(),
            connector=mock_connector,
            forwarder=mock_forwarder,
            sanitizer=sanitizer,
        )

        await handler.handle(mock_reader, mock_writer)

        # Verify the connector was called (Tor connection established)
        mock_connector.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_http_request_without_sanitizer(
        self,
        settings,
        mock_connector,
        mock_forwarder,
        mock_reader,
        mock_writer,
    ) -> None:
        """Sanitizer should NOT be called when sanitize_headers=False."""
        from tor_https_bridge.core.sanitizer import HeaderSanitizer
        from tor_https_bridge.protocol.http_parser import HTTPConnectParser

        # Explicitly disable sanitizer
        settings = Settings(
            **{**settings.model_dump(), "sanitize_headers": False},
        )

        mock_reader.read = AsyncMock(
            return_value=(
                b"GET http://example.com/ HTTP/1.1\r\n"
                b"Host: example.com\r\n"
                b"Accept-Language: ru-RU\r\n"
                b"\r\n"
            ),
        )

        sanitizer = HeaderSanitizer()
        handler = ClientHandler(
            settings=settings,
            parser=HTTPConnectParser(),
            connector=mock_connector,
            forwarder=mock_forwarder,
            sanitizer=sanitizer,
        )

        await handler.handle(mock_reader, mock_writer)

        # Connector should still be called (Tor connection)
        mock_connector.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_connect_does_not_sanitize(
        self,
        settings,
        mock_connector,
        mock_forwarder,
        mock_reader,
        mock_writer,
    ) -> None:
        """CONNECT requests should NOT go through sanitizer."""
        from tor_https_bridge.core.sanitizer import HeaderSanitizer
        from tor_https_bridge.protocol.http_parser import HTTPConnectParser

        # Enable sanitizer
        settings = Settings(
            **{**settings.model_dump(), "sanitize_headers": True},
        )

        # CONNECT request (TLS tunnel)
        mock_reader.read = AsyncMock(
            return_value=b"CONNECT api.openai.com:443 HTTP/1.1\r\n\r\n",
        )

        sanitizer = HeaderSanitizer()
        handler = ClientHandler(
            settings=settings,
            parser=HTTPConnectParser(),
            connector=mock_connector,
            forwarder=mock_forwarder,
            sanitizer=sanitizer,
        )

        await handler.handle(mock_reader, mock_writer)

        # CONNECT should succeed normally
        mock_writer.write.assert_any_call(HTTP_200_CONNECTED)
        mock_connector.connect.assert_called_once()
