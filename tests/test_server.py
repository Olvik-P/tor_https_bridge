"""Tests for tor_https_bridge.core.server."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tor_https_bridge.core.server import TorHTTPSProxy


class TestTorHTTPSProxyInit:
    """Tests for TorHTTPSProxy.__init__."""

    @pytest.mark.asyncio
    async def test_init_with_defaults(self, settings) -> None:
        proxy = TorHTTPSProxy(settings)
        assert proxy._settings is settings
        assert proxy._handler is not None
        assert proxy._server is None
        assert proxy._stop_event is not None
        assert proxy._active_connections == set()

    @pytest.mark.asyncio
    async def test_init_with_custom_handler(self, settings, handler) -> None:
        proxy = TorHTTPSProxy(settings, handler=handler)
        assert proxy._handler is handler


class TestTorHTTPSProxyOnClient:
    """Tests for TorHTTPSProxy._on_client."""

    @pytest.mark.asyncio
    async def test_on_client_tracks_connection(
        self,
        settings,
        handler,
        mock_reader,
        mock_writer,
    ) -> None:
        proxy = TorHTTPSProxy(settings, handler=handler)
        handler.handle = AsyncMock()

        await proxy._on_client(mock_reader, mock_writer)

        assert (mock_reader, mock_writer) not in proxy._active_connections
        handler.handle.assert_awaited_once_with(mock_reader, mock_writer)

    @pytest.mark.asyncio
    async def test_on_client_removes_connection_on_error(
        self,
        settings,
        handler,
        mock_reader,
        mock_writer,
    ) -> None:
        proxy = TorHTTPSProxy(settings, handler=handler)
        handler.handle = AsyncMock(side_effect=RuntimeError("test error"))

        with pytest.raises(RuntimeError):
            await proxy._on_client(mock_reader, mock_writer)

        assert (mock_reader, mock_writer) not in proxy._active_connections


class TestTorHTTPSProxyStart:
    """Tests for TorHTTPSProxy.start."""

    @pytest.mark.asyncio
    async def test_start_creates_server(self, settings, handler) -> None:
        proxy = TorHTTPSProxy(settings, handler=handler)
        mock_server = AsyncMock(spec=asyncio.Server)
        mock_server.sockets = [MagicMock()]
        mock_server.sockets[0].getsockname.return_value = (
            "127.0.0.1",
            3128,
        )

        with patch(
            "asyncio.start_server",
            return_value=mock_server,
        ) as mock_start:
            # Start the server and immediately stop it
            async def _run():
                task = asyncio.create_task(proxy.start())
                await asyncio.sleep(0.01)
                proxy._stop_event.set()
                await task

            await _run()

            mock_start.assert_awaited_once()
            assert proxy._server is mock_server

    @pytest.mark.asyncio
    async def test_start_bind_error(self, settings, handler) -> None:
        proxy = TorHTTPSProxy(settings, handler=handler)

        with patch(
            "asyncio.start_server",
            side_effect=OSError("Address already in use"),
        ):
            with pytest.raises(OSError, match="Address already in use"):
                await proxy.start()


class TestTorHTTPSProxyStop:
    """Tests for TorHTTPSProxy.stop."""

    @pytest.mark.asyncio
    async def test_stop_without_server(self, settings, handler) -> None:
        proxy = TorHTTPSProxy(settings, handler=handler)
        await proxy.stop()
        assert proxy._stop_event.is_set()

    @pytest.mark.asyncio
    async def test_stop_with_server(self, settings, handler) -> None:
        proxy = TorHTTPSProxy(settings, handler=handler)
        mock_server = AsyncMock(spec=asyncio.Server)
        proxy._server = mock_server

        await proxy.stop()

        assert proxy._stop_event.is_set()
        mock_server.close.assert_called_once()
        mock_server.wait_closed.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stop_waits_for_active_connections(
        self,
        settings,
        handler,
        mock_reader,
        mock_writer,
    ) -> None:
        """Should wait for active connections to finish naturally.

        ``stop()`` no longer forcibly closes active connections to avoid
        ``ConnectionResetError`` on Windows ``ProactorEventLoop``.
        Instead it waits for :meth:`ClientHandler.handle` to finish
        (which closes the client writer in its ``finally`` block).
        """
        proxy = TorHTTPSProxy(settings, handler=handler)
        proxy._active_connections.add((mock_reader, mock_writer))

        # Stop with a timeout — if active connections never clear,
        # the loop would hang, so we simulate them clearing
        async def _stop_with_timeout():
            task = asyncio.create_task(proxy.stop())
            await asyncio.sleep(0.05)
            proxy._active_connections.clear()
            await task

        await _stop_with_timeout()

        # Writer should NOT be closed by stop()
        mock_writer.close.assert_not_called()
        mock_writer.wait_closed.assert_not_called()

    @pytest.mark.asyncio
    async def test_stop_no_active_connections(
        self,
        settings,
        handler,
    ) -> None:
        """Should complete immediately when no active connections."""
        proxy = TorHTTPSProxy(settings, handler=handler)
        await proxy.stop()
        assert proxy._stop_event.is_set()


class TestTorHTTPSProxyIntegration:
    """Integration-style tests for TorHTTPSProxy."""

    @pytest.mark.asyncio
    async def test_start_and_stop(self, settings, handler) -> None:
        proxy = TorHTTPSProxy(settings, handler=handler)
        mock_server = AsyncMock(spec=asyncio.Server)
        mock_server.sockets = [MagicMock()]
        mock_server.sockets[0].getsockname.return_value = (
            "127.0.0.1",
            3128,
        )

        with patch("asyncio.start_server", return_value=mock_server):

            async def _run():
                task = asyncio.create_task(proxy.start())
                await asyncio.sleep(0.01)
                await proxy.stop()
                await task

            await _run()

            assert proxy._stop_event.is_set()
            mock_server.close.assert_called_once()
            mock_server.wait_closed.assert_awaited()
