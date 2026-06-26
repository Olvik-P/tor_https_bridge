"""SOCKS5 client connection handler for Tor HTTPS Bridge Proxy.

Handles incoming SOCKS5 proxy connections, negotiates the SOCKS5
handshake, establishes a tunnel through Tor, and forwards data
bidirectionally.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from tor_https_bridge.config.settings import Settings
from tor_https_bridge.core.exceptions import (
    ProxyConnectionError,
    ProxyProtocolError,
    ProxyTimeoutError,
)
from tor_https_bridge.core.forwarder import DataForwarder
from tor_https_bridge.protocol.socks_adapter import TorConnector
from tor_https_bridge.protocol.socks_server import SOCKS5Protocol

logger = logging.getLogger(__name__)


class SOCKS5ClientHandler:
    """Handles a single SOCKS5 client connection.

    Performs the SOCKS5 handshake, establishes a Tor tunnel to the
    requested destination, and forwards data bidirectionally.

    Usage::

        handler = SOCKS5ClientHandler(settings)
        await handler.handle(reader, writer)

    Args:
        settings: Application settings.
        protocol: SOCKS5 protocol handler.
        connector: Tor SOCKS5 connector.
        forwarder: Bidirectional data forwarder.
    """

    def __init__(
        self,
        settings: Settings,
        protocol: Optional[SOCKS5Protocol] = None,
        connector: Optional[TorConnector] = None,
        forwarder: Optional[DataForwarder] = None,
    ) -> None:
        self._settings = settings
        self._protocol = protocol or SOCKS5Protocol(
            username=settings.socks_proxy_username,
            password=settings.socks_proxy_password,
        )
        self._connector = connector or TorConnector(settings)
        self._forwarder = forwarder or DataForwarder(settings.buffer_size)

    async def handle(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Handle a single SOCKS5 client connection.

        Args:
            reader: Client stream reader.
            writer: Client stream writer.
        """
        client_addr = writer.get_extra_info("peername")

        try:
            # ---- Step 1: SOCKS5 handshake ----
            host, port = await self._protocol.negotiate(reader, writer)

            logger.info(
                "%s: SOCKS5 connect to %s:%d",
                client_addr,
                host,
                port,
            )

            # ---- Step 2: Establish Tor tunnel ----
            conn = await self._connector.connect(host, port)
            async with conn as tor_sock:
                tor_reader, tor_writer = await asyncio.open_connection(
                    sock=tor_sock,
                )

                try:
                    # ---- Step 3: Bidirectional forwarding ----
                    await self._forwarder.forward_bidirectional(
                        (reader, writer),
                        (tor_reader, tor_writer),
                    )
                finally:
                    try:
                        tor_writer.close()
                        await tor_writer.wait_closed()
                    except (ConnectionError, OSError):
                        pass

        except asyncio.TimeoutError:
            logger.warning(
                "%s: SOCKS5 request timeout (%ds)",
                client_addr,
                self._settings.read_timeout,
            )

        except ProxyProtocolError as e:
            logger.warning(
                "%s: SOCKS5 protocol error - %s",
                client_addr,
                e,
            )

        except (ProxyConnectionError, ProxyTimeoutError) as e:
            logger.warning(
                "%s: SOCKS5 upstream error - %s",
                client_addr,
                e,
            )

        except (ConnectionError, OSError) as e:
            logger.debug(
                "%s: SOCKS5 connection error - %s",
                client_addr,
                e,
            )

        except GeneratorExit:
            logger.debug(
                "%s: SOCKS5 connection cancelled (GeneratorExit)",
                client_addr,
            )

        except asyncio.CancelledError:
            logger.debug("%s: SOCKS5 connection cancelled", client_addr)
            raise

        except Exception as e:
            logger.error(
                "%s: SOCKS5 unexpected error - %s",
                client_addr,
                e,
                exc_info=True,
            )

        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except GeneratorExit:
                try:
                    writer.close()
                except (ConnectionError, OSError):
                    pass
            except (ConnectionError, OSError):
                pass
