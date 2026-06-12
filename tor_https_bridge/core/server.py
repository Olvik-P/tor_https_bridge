"""Main proxy server for Tor HTTPS Bridge."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from tor_https_bridge.config.constants import BUFFER_MULTIPLIER
from tor_https_bridge.config.settings import Settings
from tor_https_bridge.core.handler import ClientHandler

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
    """Main proxy server handling HTTPS CONNECT requests.

    Listens for incoming HTTPS proxy connections, delegates each
    connection to a :class:`ClientHandler`, and manages graceful
    shutdown of all active connections.

    Usage::

        proxy = TorHTTPSProxy(settings)
        await proxy.start()

    Args:
        settings: Application settings.
        handler: Optional custom client handler (injected for testing).
    """

    def __init__(
        self,
        settings: Settings,
        handler: Optional[ClientHandler] = None,
    ) -> None:
        self._settings = settings
        self._handler = handler or ClientHandler(settings)
        self._server: Optional[asyncio.Server] = None
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

        Tracks the connection in ``_active_connections`` for graceful
        shutdown, delegates to :class:`ClientHandler`, and removes the
        connection from tracking when done.

        Args:
            reader: Client stream reader.
            writer: Client stream writer.
        """
        conn_key = (reader, writer)
        self._active_connections.add(conn_key)
        try:
            await self._handler.handle(reader, writer)
        except asyncio.CancelledError:
            # When the event loop is shutting down, pending tasks are
            # cancelled.  Re-raise so the task machinery can clean up.
            raise
        finally:
            self._active_connections.discard(conn_key)
            # Ensure the client writer is closed even on cancellation
            try:
                writer.close()
            except OSError:
                pass

    async def start(self) -> None:
        """Start the proxy server.

        Creates an :class:`asyncio.Server` listening on the configured
        host and port, then waits for the stop event to be set.

        Raises:
            OSError: If the server cannot bind to the address.
        """
        self._server = await asyncio.start_server(
            self._on_client,
            host=self._settings.https_proxy_host,
            port=self._settings.https_proxy_port,
            backlog=self._settings.backlog,
            limit=self._settings.buffer_size * BUFFER_MULTIPLIER,
        )

        addr = self._server.sockets[0].getsockname()
        logger.info("Server started on %s:%d", addr[0], addr[1])

        async with self._server:
            await self._stop_event.wait()

    async def stop(self) -> None:
        """Gracefully stop the server.

        Sets the stop event, closes the server socket to stop accepting
        new connections, and waits for all active connections to finish.

        This method is idempotent — calling it multiple times is safe.

        Active connections are **not** forcibly closed here because
        :meth:`ClientHandler.handle` already closes the client writer in
        its ``finally`` block.  Closing it again from here would trigger
        ``ConnectionResetError`` on Windows ``ProactorEventLoop``
        (double-close on the same transport).
        """
        if self._stop_event.is_set():
            # Already stopping — prevent re-entrance
            return

        logger.info("Stopping server...")
        self._stop_event.set()

        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

        # Wait for active connections to finish naturally
        # (ClientHandler.handle() closes the client writer in finally)
        if self._active_connections:
            logger.info(
                "Waiting for %d active connection(s) to finish...",
                len(self._active_connections),
            )
            # Use a timeout to avoid hanging forever on misbehaving
            # connections during shutdown
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
