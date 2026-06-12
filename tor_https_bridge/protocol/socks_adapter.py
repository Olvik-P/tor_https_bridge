"""SOCKS5 adapter for connecting to Tor."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional, Protocol

import socks

from tor_https_bridge.config.settings import Settings
from tor_https_bridge.core.exceptions import (
    ProxyConnectionError,
    ProxyTimeoutError,
)

logger = logging.getLogger(__name__)


class TorConnectorProtocol(Protocol):
    """Protocol for Tor SOCKS5 connector implementations."""

    @asynccontextmanager
    async def connect(
        self,
        host: str,
        port: int,
    ) -> AsyncIterator[socks.socksocket]:
        """Async context manager for Tor SOCKS5 connection.

        Args:
            host: Target hostname.
            port: Target port.

        Yields:
            Connected SOCKS5 socket.

        Raises:
            ProxyConnectionError: If connection to Tor fails.
            ProxyTimeoutError: If connection times out.
        """
        ...


class TorConnector:
    """Manages SOCKS5 connections through Tor.

    Uses :func:`asyncio.get_running_loop().run_in_executor` to perform
    blocking :class:`socks.socksocket` operations without blocking the
    event loop.

    Implements automatic retry on connection failures to handle
    transient Tor circuit issues.

    Usage::

        connector = TorConnector(settings)
        async with connector.connect('example.com', 443) as sock:
            reader, writer = await asyncio.open_connection(sock=sock)

    Args:
        settings: Application settings with Tor SOCKS5 configuration.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    @asynccontextmanager
    async def connect(
        self,
        host: str,
        port: int,
    ) -> AsyncIterator[socks.socksocket]:
        """Async context manager for Tor SOCKS5 connection.

        Creates a SOCKS5 socket via Tor and yields it. The socket is
        automatically closed when the context manager exits.

        Implements automatic retry with configurable delay on transient
        connection failures.

        Args:
            host: Target hostname.
            port: Target port.

        Yields:
            Connected SOCKS5 socket.

        Raises:
            ProxyConnectionError: If connection to Tor fails after all
                retry attempts.
            ProxyTimeoutError: If connection times out.
        """
        sock: Optional[socks.socksocket] = None
        last_error: Optional[Exception] = None

        retries = self._settings.socks_retry_count
        for attempt in range(1, retries + 2):  # +1 for the initial attempt
            try:
                sock = await self._create_socket(host, port)
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
                continue  # Try next attempt

            # Socket created successfully — yield to caller
            try:
                yield sock
            finally:
                # Ensure socket is closed when the caller exits the context
                try:
                    sock.close()
                except OSError:
                    pass
                sock = None

            return  # Success — exit context manager

        # All attempts exhausted
        raise ProxyConnectionError(
            f"Failed to connect to {host}:{port} via Tor "
            f"after {retries + 1} attempt(s): {last_error}",
        ) from last_error

    async def _create_socket(self, host: str, port: int) -> socks.socksocket:
        """Create and connect a SOCKS5 socket (runs in executor).

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
