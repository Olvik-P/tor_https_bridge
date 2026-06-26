"""Main proxy server for Tor HTTPS Bridge.

Supports both HTTPS CONNECT and SOCKS5 proxy protocols on a single
listen port with automatic protocol detection.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from tor_https_bridge.config.constants import BUFFER_MULTIPLIER
from tor_https_bridge.config.settings import Settings
from tor_https_bridge.core.handler import ClientHandler
from tor_https_bridge.core.socks_handler import SOCKS5ClientHandler
from tor_https_bridge.protocol.socks_server import peek_protocol

logger = logging.getLogger(__name__)


def _suppress_proactor_connection_reset(
    loop: asyncio.AbstractEventLoop,
    context: dict,
) -> None:
    """Suppress known benign errors from Windows ``ProactorEventLoop``.

    On Windows ``ProactorEventLoop``, certain errors can occur during
    normal connection teardown:

    * ``ConnectionResetError [WinError 10054]`` — when a transport is
      closed twice (e.g. the handler closes the writer and the proactor
      also fires ``_call_connection_lost``).
    * ``OSError [WinError 6]`` (The handle is invalid) — when an
      overlapped I/O operation is cancelled after the underlying socket
      has already been closed.

    This handler silently swallows these specific errors so they do not
    flood the logs. All other exceptions are logged normally.
    """
    exc = context.get("exception")
    if isinstance(exc, ConnectionResetError) and exc.winerror == 10054:
        logger.debug(
            "Suppressed WinError 10054 (connection reset on double-close)",
        )
        return
    if isinstance(exc, OSError) and exc.winerror == 6:
        logger.debug(
            "Suppressed WinError 6 (invalid handle on overlapped cancel)",
        )
        return
    # Fall back to default handler for everything else
    loop.default_exception_handler(context)


class TorHTTPSProxy:
    """Main proxy server handling HTTPS CONNECT and SOCKS5 requests.

    Listens for incoming proxy connections on the configured host and
    port, automatically detects whether the client speaks HTTPS CONNECT
    or SOCKS5, and delegates to the appropriate handler.

    Can also listen on separate ports for each protocol if configured.

    Usage::

        proxy = TorHTTPSProxy(settings)
        await proxy.start()

    Args:
        settings: Application settings.
        https_handler: Optional custom HTTPS client handler (injected
            for testing).
        socks_handler: Optional custom SOCKS5 client handler (injected
            for testing).
    """

    def __init__(
        self,
        settings: Settings,
        https_handler: Optional[ClientHandler] = None,
        socks_handler: Optional[SOCKS5ClientHandler] = None,
    ) -> None:
        self._settings = settings
        self._https_handler = https_handler or ClientHandler(settings)
        self._socks_handler = socks_handler or SOCKS5ClientHandler(settings)
        self._servers: list[asyncio.Server] = []
        self._stop_event = asyncio.Event()
        self._active_connections: set[
            tuple[asyncio.StreamReader, asyncio.StreamWriter]
        ] = set()

        # Install global exception handler to suppress WinError 10054
        # on Windows ProactorEventLoop (double-close on transports).
        loop = asyncio.get_running_loop()
        loop.set_exception_handler(_suppress_proactor_connection_reset)

    async def _on_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Callback for each new client connection.

        Detects the protocol (SOCKS5 vs HTTP) and delegates to the
        appropriate handler.

        Tracks the connection in ``_active_connections`` for graceful
        shutdown, and removes the connection from tracking when done.

        All exceptions are caught and logged to prevent propagation
        into ``StreamReaderProtocol``, which would cause "cannot reuse
        already awaited coroutine" errors on Python 3.13+.

        Args:
            reader: Client stream reader.
            writer: Client stream writer.
        """
        conn_key = (reader, writer)
        self._active_connections.add(conn_key)
        try:
            # Detect protocol by peeking at the first byte
            protocol = await peek_protocol(reader)

            if protocol == "socks5":
                await self._socks_handler.handle(reader, writer)
            else:
                await self._https_handler.handle(reader, writer)

        except GeneratorExit:
            # Python 3.13+ on Windows ProactorEventLoop may raise
            # GeneratorExit during task cancellation.  Do NOT re-raise
            # it — doing so would corrupt the StreamReaderProtocol and
            # cause "cannot reuse already awaited coroutine" errors.
            # Simply exit the coroutine cleanly.
            logger.debug(
                "Client connection cancelled (GeneratorExit)",
            )
        except asyncio.CancelledError:
            # When the event loop is shutting down, pending tasks are
            # cancelled.  Do NOT re-raise — the task machinery will
            # handle cleanup. Re-raising CancelledError here can cause
            # "coroutine ignored GeneratorExit" on Python 3.13+.
            logger.debug(
                "Client connection cancelled (CancelledError)",
            )
        except Exception:
            # Catch any unexpected exception from the handler to
            # prevent propagation into StreamReaderProtocol.
            # The handler itself already catches and logs most errors,
            # but this is a safety net for anything that slips through.
            logger.debug(
                "Client connection error",
                exc_info=True,
            )
        finally:
            self._active_connections.discard(conn_key)
            # Ensure the client writer is closed even on cancellation.
            # writer.close() is synchronous and should not raise
            # GeneratorExit, but guard against it just in case.
            try:
                writer.close()
            except GeneratorExit:
                pass
            except OSError:
                pass

    async def _start_single_server(
        self,
        host: str,
        port: int,
        label: str,
    ) -> asyncio.Server:
        """Start a single listen server.

        Args:
            host: Listen host.
            port: Listen port.
            label: Human-readable label for logging.

        Returns:
            The started asyncio.Server instance.

        Raises:
            OSError: If the server cannot bind to the address.
        """
        server = await asyncio.start_server(
            self._on_client,
            host=host,
            port=port,
            backlog=self._settings.backlog,
            limit=self._settings.buffer_size * BUFFER_MULTIPLIER,
        )
        addr = server.sockets[0].getsockname()
        logger.info("%s server started on %s:%d", label, addr[0], addr[1])
        return server

    async def start(self) -> None:
        """Start the proxy server(s).

        Creates one or more :class:`asyncio.Server` instances listening
        on the configured hosts and ports, then waits for the stop event
        to be set.

        Raises:
            OSError: If a server cannot bind to its address.
        """
        # Start HTTPS CONNECT proxy if enabled
        if self._settings.https_proxy_enabled:
            https_server = await self._start_single_server(
                self._settings.https_proxy_host,
                self._settings.https_proxy_port,
                "HTTPS proxy",
            )
            self._servers.append(https_server)

        # Start SOCKS5 proxy if enabled
        if self._settings.socks_proxy_enabled:
            socks_server = await self._start_single_server(
                self._settings.socks_proxy_host,
                self._settings.socks_proxy_port,
                "SOCKS5 proxy",
            )
            self._servers.append(socks_server)

        if not self._servers:
            logger.warning(
                "No proxy servers are enabled — nothing to listen on")

        # Wait for stop event
        await self._stop_event.wait()

    async def stop(self) -> None:
        """Gracefully stop all servers.

        Sets the stop event, closes all server sockets to stop accepting
        new connections, and waits for all active connections to finish.

        This method is idempotent — calling it multiple times is safe.

        Active connections are **not** forcibly closed here because
        the handlers already close the client writer in their
        ``finally`` blocks.  Closing it again from here would trigger
        ``ConnectionResetError`` on Windows ``ProactorEventLoop``
        (double-close on the same transport).
        """
        if self._stop_event.is_set():
            # Already stopping — prevent re-entrance
            return

        logger.info("Stopping server...")
        self._stop_event.set()

        for server in self._servers:
            server.close()
            await server.wait_closed()

        self._servers.clear()

        # Wait for active connections to finish naturally
        if self._active_connections:
            logger.info(
                "Waiting for %d active connection(s) to finish...",
                len(self._active_connections),
            )
            wait_start = asyncio.get_running_loop().time()
            while self._active_connections:
                elapsed = asyncio.get_running_loop().time() - wait_start
                if elapsed > 30.0:
                    logger.warning(
                        "Shutdown timeout reached "
                        "(%d active connections remain)",
                        len(self._active_connections),
                    )
                    break
                await asyncio.sleep(0.1)

        logger.info("Server stopped")
