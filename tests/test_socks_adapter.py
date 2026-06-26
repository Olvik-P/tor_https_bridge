"""Tests for tor_https_bridge.protocol.socks_adapter."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest
import socks

from tor_https_bridge.config.settings import Settings
from tor_https_bridge.core.exceptions import (
    ProxyConnectionError,
    ProxyTimeoutError,
)
from tor_https_bridge.protocol.socks_adapter import TorConnector


class TestTorConnectorInit:
    """Tests for TorConnector.__init__."""

    def test_init_with_settings(self, settings) -> None:
        connector = TorConnector(settings)
        assert connector._settings == settings
        assert connector._loop is None


class TestTorConnectorBlockingConnect:
    """Tests for TorConnector._blocking_connect."""

    def test_blocking_connect_success(self, settings) -> None:
        connector = TorConnector(settings)
        mock_sock = MagicMock(spec=socks.socksocket)

        with patch("socks.socksocket", return_value=mock_sock):
            result = connector._blocking_connect("example.com", 443)

            assert result is mock_sock
            mock_sock.set_proxy.assert_called_once_with(
                socks.SOCKS5,
                settings.tor_socks_host,
                settings.tor_socks_port,
            )
            mock_sock.settimeout.assert_any_call(settings.connect_timeout)
            mock_sock.connect.assert_called_once_with(("example.com", 443))
            # settimeout should be called twice (connect + read timeout)
            assert mock_sock.settimeout.call_count == 2

    def test_blocking_connect_failure_closes_socket(self, settings) -> None:
        connector = TorConnector(settings)
        mock_sock = MagicMock(spec=socks.socksocket)
        mock_sock.connect.side_effect = ConnectionError("connection refused")

        with patch("socks.socksocket", return_value=mock_sock):
            with pytest.raises(ConnectionError):
                connector._blocking_connect("example.com", 443)

            mock_sock.close.assert_called_once()


class TestTorConnectorCreateSocket:
    """Tests for TorConnector._create_socket."""

    @pytest.mark.asyncio
    async def test_create_socket_success(self, settings) -> None:
        connector = TorConnector(settings)
        mock_sock = MagicMock(spec=socks.socksocket)

        with patch.object(
            connector,
            "_blocking_connect",
            return_value=mock_sock,
        ):
            result = await connector._create_socket("example.com", 443)
            assert result is mock_sock

    @pytest.mark.asyncio
    async def test_create_socket_timeout(self, settings) -> None:
        # Use a short connect_timeout to trigger timeout
        fast_timeout_settings = Settings(
            tor_socks_host="127.0.0.1",
            tor_socks_port=9050,
            connect_timeout=1,
        )
        connector = TorConnector(fast_timeout_settings)

        def _slow_connect(*args, **kwargs):
            import time

            time.sleep(10)
            return MagicMock()  # pragma: no cover

        with patch.object(
            connector,
            "_blocking_connect",
            side_effect=_slow_connect,
        ):
            with pytest.raises(ProxyTimeoutError, match="timed out"):
                await connector._create_socket("example.com", 443)


class TestTorConnectorConnect:
    """Tests for TorConnector.connect context manager."""

    @pytest.mark.asyncio
    async def test_connect_success(self, settings) -> None:
        connector = TorConnector(settings)
        mock_sock = MagicMock(spec=socks.socksocket)

        with patch.object(connector, "_do_create_socket", return_value=mock_sock):
            conn = await connector.connect("example.com", 443)
            async with conn as sock:
                assert sock is mock_sock

            mock_sock.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_connection_error_after_retries(
        self,
        settings,
    ) -> None:
        """Should retry and then raise after all attempts exhausted."""
        connector = TorConnector(settings)

        with patch.object(
            connector,
            "_do_create_socket",
            side_effect=ConnectionError("connection refused"),
        ) as mock_create:
            with pytest.raises(
                ProxyConnectionError,
                match="Failed to connect",
            ):
                conn = await connector.connect("example.com", 443)
                async with conn:
                    pass  # pragma: no cover

            # Should have been called: initial + retry_count attempts
            assert mock_create.call_count == settings.socks_retry_count + 1

    @pytest.mark.asyncio
    async def test_connect_os_error_after_retries(self, settings) -> None:
        connector = TorConnector(settings)

        with patch.object(
            connector,
            "_do_create_socket",
            side_effect=OSError("socket error"),
        ) as mock_create:
            with pytest.raises(
                ProxyConnectionError,
                match="Failed to connect",
            ):
                conn = await connector.connect("example.com", 443)
                async with conn:
                    pass  # pragma: no cover

            assert mock_create.call_count == settings.socks_retry_count + 1

    @pytest.mark.asyncio
    async def test_connect_timeout_error_after_retries(self, settings) -> None:
        connector = TorConnector(settings)

        with patch.object(
            connector,
            "_do_create_socket",
            side_effect=asyncio.TimeoutError("timed out"),
        ) as mock_create:
            with pytest.raises(
                ProxyConnectionError,
                match="Failed to connect",
            ):
                conn = await connector.connect("example.com", 443)
                async with conn:
                    pass  # pragma: no cover

            assert mock_create.call_count == settings.socks_retry_count + 1

    @pytest.mark.asyncio
    async def test_connect_success_on_retry(self, settings) -> None:
        """Should succeed on the second attempt after first failure."""
        connector = TorConnector(settings)
        mock_sock = MagicMock(spec=socks.socksocket)

        # First call fails, second succeeds
        with patch.object(
            connector,
            "_do_create_socket",
            side_effect=[ConnectionError("first fail"), mock_sock],
        ):
            conn = await connector.connect("example.com", 443)
            async with conn as sock:
                assert sock is mock_sock

            mock_sock.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_socket_close_on_exception(self, settings) -> None:
        """Socket closed even if exception occurs in the context."""
        connector = TorConnector(settings)
        mock_sock = MagicMock(spec=socks.socksocket)

        with patch.object(connector, "_do_create_socket", return_value=mock_sock):
            conn = await connector.connect("example.com", 443)
            with pytest.raises(RuntimeError):
                async with conn:
                    raise RuntimeError("test error")

            mock_sock.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_socket_close_error_suppressed(
        self,
        settings,
    ) -> None:
        """Socket close errors should be suppressed."""
        connector = TorConnector(settings)
        mock_sock = MagicMock(spec=socks.socksocket)
        mock_sock.close.side_effect = OSError("close error")

        with patch.object(connector, "_do_create_socket", return_value=mock_sock):
            conn = await connector.connect("example.com", 443)
            async with conn as sock:
                assert sock is mock_sock

            mock_sock.close.assert_called_once()


class TestTorConnectorLoopCaching:
    """Tests for event loop caching in TorConnector."""

    @pytest.mark.asyncio
    async def test_loop_is_cached(self, settings) -> None:
        connector = TorConnector(settings)
        assert connector._loop is None

        mock_sock = MagicMock(spec=socks.socksocket)
        with patch.object(
            connector,
            "_blocking_connect",
            return_value=mock_sock,
        ):
            await connector._create_socket("example.com", 443)
            assert connector._loop is not None
            assert connector._loop is asyncio.get_running_loop()
