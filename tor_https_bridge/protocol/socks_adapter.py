"""SOCKS5 adapter for connecting to Tor."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional, Protocol

import socks

from tor_https_bridge.config.settings import Settings
from tor_https_bridge.core.exceptions import (
    ProxyConnectionError,
    ProxyTimeoutError,
)

logger = logging.getLogger(__name__)


class TorConnectorProtocol(Protocol):
    """Protocol for Tor SOCKS5 connector implementations."""

    async def connect(
        self,
        host: str,
        port: int,
    ) -> "TorConnection":
        """Create a Tor SOCKS5 connection context manager.

        Args:
            host: Target hostname.
            port: Target port.

        Returns:
            TorConnection context manager.
        """
        ...


class TorConnection:
    """Async context manager for a single Tor SOCKS5 connection.

    Uses ``__aenter__`` / ``__aexit__`` instead of
    ``@asynccontextmanager`` to avoid ``GeneratorExit`` propagation
    issues on Python 3.13 + Windows ``ProactorEventLoop``.

    Usage::

        conn = TorConnection(connector, "example.com", 443)
        async with conn as sock:
            reader, writer = await asyncio.open_connection(sock=sock)

    Args:
        connector: Parent TorConnector instance.
        host: Target hostname.
        port: Target port.
    """

    def __init__(
        self,
        connector: "TorConnector",
        host: str,
        port: int,
    ) -> None:
        self._connector = connector
        self._host = host
        self._port = port
        self._sock: Optional[socks.socksocket] = None

    async def __aenter__(self) -> socks.socksocket:
        """Create and return a connected SOCKS5 socket."""
        self._sock = await self._connector._create_socket(
            self._host, self._port,
        )
        return self._sock

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[object],
    ) -> Optional[bool]:
        """Close the SOCKS5 socket on exit.

        Handles ``GeneratorExit`` gracefully — closes the socket and
        suppresses the exception to prevent propagation into
        ``StreamReaderProtocol``.
        """
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

        # Suppress GeneratorExit to prevent "coroutine ignored
        # GeneratorExit" errors on Python 3.13 + Windows.
        if exc_type is GeneratorExit:
            logger.debug(
                "Tor connection to %s:%s closed during cancellation",
                self._host,
                self._port,
            )
            return True  # Suppress the exception

        return None  # Do not suppress other exceptions


class TorConnector:
    """Manages SOCKS5 connections through Tor.

    Uses :func:`asyncio.get_running_loop().run_in_executor` to perform
    blocking :class:`socks.socksocket` operations without blocking the
    event loop.

    Implements automatic retry on connection failures to handle
    transient Tor circuit issues.

    Usage::

        connector = TorConnector(settings)
        conn = await connector.connect('example.com', 443)
        async with conn as sock:
            reader, writer = await asyncio.open_connection(sock=sock)

    Args:
        settings: Application settings with Tor SOCKS5 configuration.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def connect(
        self,
        host: str,
        port: int,
    ) -> TorConnection:
        """Create a Tor SOCKS5 connection context manager.

        Returns a :class:`TorConnection` that, when used as an async
        context manager, creates a SOCKS5 socket via Tor and yields it.
        The socket is automatically closed when the context manager
        exits.

        Implements automatic retry with configurable delay on transient
        connection failures.

        Args:
            host: Target hostname.
            port: Target port.

        Returns:
            TorConnection context manager (not yet connected —
            connection happens in ``__aenter__``).
        """
        # Note: connection is deferred to __aenter__ so that retry
        # logic runs inside the context manager, not here.
        return TorConnection(self, host, port)

    async def _create_socket(self, host: str, port: int) -> socks.socksocket:
        """Create and connect a SOCKS5 socket (runs in executor).

        Implements automatic retry with configurable delay on transient
        connection failures.

        Args:
            host: Target hostname.
            port: Target port.

        Returns:
            Connected SOCKS5 socket.

        Raises:
            ProxyConnectionError: If connection to Tor fails after all
                retry attempts.
            ProxyTimeoutError: If connection times out.
        """
        last_error: Optional[Exception] = None
        retries = self._settings.socks_retry_count

        for attempt in range(1, retries + 2):  # +1 for the initial attempt
            try:
                return await self._do_create_socket(host, port)
            except (ConnectionError, OSError, asyncio.TimeoutError) as e:
                last_error = e
                if attempt <= retries:
                    logger.debug(
                        "Connection attempt %d/%d to %s:%s failed: %s. "
                        "Retrying in %.1fs...",
                        attempt,
                        retries + 1,
                        host,
                        port,
                        e,
                        self._settings.socks_retry_delay,
                    )
                    await asyncio.sleep(self._settings.socks_retry_delay)
                else:
                    logger.debug(
                        "All %d connection attempts to %s:%s failed.",
                        retries + 1,
                        host,
                        port,
                    )

        raise ProxyConnectionError(
            f"Failed to connect to {host}:{port} via Tor "
            f"after {retries + 1} attempt(s): {last_error}",
        ) from last_error

    async def _do_create_socket(
        self, host: str, port: int,
    ) -> socks.socksocket:
        """Single attempt at creating a SOCKS5 socket (runs in executor).

        Args:
            host: Target hostname.
            port: Target port.

        Returns:
            Connected SOCKS5 socket.

        Raises:
            ProxyTimeoutError: If the connection times out.
        """
        if self._loop is None:
            self._loop = asyncio.get_running_loop()

        # Use a future to track the blocking connect task
        # so we can cancel it on timeout and close the socket
        connect_future = self._loop.run_in_executor(
            None,
            self._blocking_connect,
            host,
            port,
        )

        try:
            sock = await asyncio.wait_for(
                connect_future,
                timeout=self._settings.connect_timeout,
            )
            return sock
        except asyncio.TimeoutError as e:
            # Cancel the connect task to stop the blocking call
            connect_future.cancel()
            raise ProxyTimeoutError(
                f"Connection to {host}:{port} timed out after "
                f"{self._settings.connect_timeout}s",
            ) from e

    def _blocking_connect(self, host: str, port: int) -> socks.socksocket:
        """Blocking SOCKS5 socket creation (runs in thread pool).

        Args:
            host: Target hostname.
            port: Target port.

        Returns:
            Connected SOCKS5 socket.
        """
        sock = socks.socksocket()
        try:
            sock.set_proxy(
                socks.SOCKS5,
                self._settings.tor_socks_host,
                self._settings.tor_socks_port,
            )
            sock.settimeout(self._settings.connect_timeout)
            sock.connect((host, port))
            sock.settimeout(self._settings.read_timeout)
            return sock
        except Exception:
            try:
                sock.close()
            except OSError:
                pass
            raise
