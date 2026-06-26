"""Client connection handler for Tor HTTPS Bridge Proxy."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

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
from tor_https_bridge.core.forwarder import DataForwarder
from tor_https_bridge.core.sanitizer import HeaderSanitizer
from tor_https_bridge.protocol.http_parser import HTTPConnectParser
from tor_https_bridge.protocol.socks_adapter import TorConnector

logger = logging.getLogger(__name__)


class ClientHandler:
    """Handles a single HTTPS CONNECT client connection.

    Reads the HTTP CONNECT request, establishes a tunnel through Tor,
    and forwards data bidirectionally between the client and the
    upstream destination.

    Usage::

        handler = ClientHandler(settings)
        await handler.handle(reader, writer)

    Args:
        settings: Application settings.
        parser: HTTP CONNECT request parser.
        connector: Tor SOCKS5 connector.
        forwarder: Bidirectional data forwarder.
    """

    def __init__(
        self,
        settings: Settings,
        parser: Optional[HTTPConnectParser] = None,
        connector: Optional[TorConnector] = None,
        forwarder: Optional[DataForwarder] = None,
        sanitizer: Optional[HeaderSanitizer] = None,
    ) -> None:
        self._settings = settings
        self._parser = parser or HTTPConnectParser()
        self._connector = connector or TorConnector(settings)
        self._forwarder = forwarder or DataForwarder(settings.buffer_size)
        self._sanitizer = sanitizer or HeaderSanitizer(
            override_user_agent=settings.override_user_agent,
            override_accept_language=settings.override_accept_language,
        )

    async def _handle_connect(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        host: str,
        port: int,
        client_addr: tuple,
    ) -> None:
        """Handle a CONNECT request — establish tunnel and forward data.

        Args:
            reader: Client stream reader.
            writer: Client stream writer.
            host: Target hostname.
            port: Target port.
            client_addr: Client address for logging.
        """
        logger.info("%s: Connecting to %s:%d", client_addr, host, port)

        writer.write(HTTP_200_CONNECTED)
        await writer.drain()

        try:
            conn = await self._connector.connect(host, port)
            async with conn as tor_sock:
                tor_reader, tor_writer = await asyncio.open_connection(
                    sock=tor_sock,
                )

                try:
                    await self._forwarder.forward_bidirectional(
                        (reader, writer),
                        (tor_reader, tor_writer),
                    )
                finally:
                    # Close the Tor writer to release the transport before
                    # the SOCKS5 socket is closed by the context manager.
                    try:
                        tor_writer.close()
                        await tor_writer.wait_closed()
                    except (ConnectionError, OSError):
                        pass
        except asyncio.CancelledError:
            logger.debug(
                "%s: Connect cancelled during shutdown",
                client_addr,
            )
            raise

    async def _handle_http_request(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        request_data: bytes,
        host: str,
        port: int,
        client_addr: tuple,
    ) -> None:
        """Handle a plain HTTP request (GET, POST, etc.) via Tor tunnel.

        Reads the HTTP request, establishes a Tor connection to the target,
        forwards the request, and relays the response back to the client.

        Args:
            reader: Client stream reader.
            writer: Client stream writer.
            request_data: The raw HTTP request bytes.
            host: Target hostname.
            port: Target port.
            client_addr: Client address for logging.
        """
        logger.info(
            "%s: Tunneling HTTP request to %s:%d", client_addr, host, port
        )

        # Sanitize headers in stealth mode to remove identifying
        # information (locale, OS, internal IPs, etc.)
        if self._settings.sanitize_headers:
            request_data = self._sanitizer.sanitize(request_data)
            logger.debug(
                "%s: Sanitized headers for %s:%d", client_addr, host, port
            )

        try:
            conn = await self._connector.connect(host, port)
            async with conn as tor_sock:
                tor_reader, tor_writer = await asyncio.open_connection(
                    sock=tor_sock,
                )

                try:
                    # Forward the initial HTTP request to the target
                    tor_writer.write(request_data)
                    await tor_writer.drain()

                    # Forward response back to client, then continue
                    # bidirectional forwarding
                    response_data = await tor_reader.read(
                        self._settings.buffer_size,
                    )
                    if response_data:
                        writer.write(response_data)
                        await writer.drain()

                    await self._forwarder.forward_bidirectional(
                        (reader, writer),
                        (tor_reader, tor_writer),
                    )
                finally:
                    # Close the Tor writer to release the transport before
                    # the SOCKS5 socket is closed by the context manager.
                    try:
                        tor_writer.close()
                        await tor_writer.wait_closed()
                    except (ConnectionError, OSError):
                        pass
        except asyncio.CancelledError:
            logger.debug(
                "%s: HTTP request cancelled during shutdown",
                client_addr,
            )
            raise

    async def handle(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Handle a single client connection.

        Args:
            reader: Client stream reader.
            writer: Client stream writer.
        """
        client_addr = writer.get_extra_info("peername")

        try:
            request_data = await self._parser.read_request(
                reader,
                self._settings.max_request_size,
                timeout=self._settings.read_timeout,
            )
            host, port, method = self._parser.parse_connect(request_data)

            if method == "CONNECT":
                await self._handle_connect(
                    reader,
                    writer,
                    host,
                    port,
                    client_addr,
                )
            else:
                await self._handle_http_request(
                    reader,
                    writer,
                    request_data,
                    host,
                    port,
                    client_addr,
                )

        except asyncio.TimeoutError:
            logger.warning(
                "%s: Request read timeout (%ds)",
                client_addr,
                self._settings.read_timeout,
            )

        except ProxyProtocolError as e:
            logger.warning("%s: Protocol error - %s", client_addr, e)
            try:
                writer.write(HTTP_400_BAD_REQUEST)
                await writer.drain()
            except (ConnectionError, OSError):
                pass

        except (ProxyConnectionError, ProxyTimeoutError) as e:
            logger.warning("%s: Upstream error - %s", client_addr, e)
            try:
                writer.write(HTTP_502_BAD_GATEWAY)
                await writer.drain()
            except (ConnectionError, OSError):
                pass

        except (ConnectionError, OSError) as e:
            logger.debug("%s: Connection error - %s", client_addr, e)

        except GeneratorExit:
            # GeneratorExit is raised when the task is cancelled during
            # shutdown on Python 3.13+.  Do NOT re-raise — the caller
            # (_on_client) handles it and must not propagate it to
            # asyncio's StreamReaderProtocol.
            logger.debug(
                "%s: Connection cancelled (GeneratorExit)", client_addr
            )

        except asyncio.CancelledError:
            # CancelledError is raised when the task is cancelled during
            # shutdown.  Re-raise so the event loop can handle it properly.
            logger.debug("%s: Connection cancelled", client_addr)
            raise

        except Exception as e:
            logger.error(
                "%s: Unexpected error - %s",
                client_addr,
                e,
                exc_info=True,
            )

        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except GeneratorExit:
                # GeneratorExit during shutdown — close synchronously
                # and suppress to prevent propagation into
                # StreamReaderProtocol.
                try:
                    writer.close()
                except (ConnectionError, OSError):
                    pass
            except (ConnectionError, OSError):
                pass
