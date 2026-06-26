"""SOCKS5 server protocol implementation.

Implements the SOCKS5 protocol (RFC 1928) for accepting incoming SOCKS5
proxy connections.  Supports:

* ``NO AUTHENTICATION REQUIRED`` (method ``0x00``).
* ``USERNAME/PASSWORD`` authentication (RFC 1929, method ``0x02``).
* ``CONNECT`` command (``0x01``).
* ``DOMAINNAME``, ``IPv4``, and ``IPv6`` address types.

Usage::

    parser = SOCKS5Protocol()
    host, port = await parser.negotiate(reader, writer)
    # host, port are the target the client wants to connect to
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import struct
from typing import Optional

from tor_https_bridge.core.exceptions import ProxyProtocolError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SOCKS5 constants
# ---------------------------------------------------------------------------

SOCKS_VERSION: int = 0x05
"""SOCKS protocol version 5."""

# --- Authentication methods ---
AUTH_NONE: int = 0x00
"""No authentication required."""
AUTH_GSSAPI: int = 0x01
"""GSSAPI authentication."""
AUTH_USERNAME_PASSWORD: int = 0x02
"""Username/password authentication (RFC 1929)."""
AUTH_NO_ACCEPTABLE: int = 0xFF
"""No acceptable method."""

# --- Commands ---
CMD_CONNECT: int = 0x01
"""CONNECT command."""
CMD_BIND: int = 0x02
"""BIND command."""
CMD_UDP_ASSOCIATE: int = 0x03
"""UDP ASSOCIATE command."""

# --- Address types ---
ATYP_IPV4: int = 0x01
"""IPv4 address (4 bytes)."""
ATYP_DOMAINNAME: int = 0x02
"""Domain name (1-byte length prefix + name)."""
ATYP_IPV6: int = 0x04
"""IPv6 address (16 bytes)."""

# --- Reply codes ---
REP_SUCCESS: int = 0x00
"""Succeeded."""
REP_GENERAL_FAILURE: int = 0x01
"""General SOCKS server failure."""
REP_CONNECTION_NOT_ALLOWED: int = 0x02
"""Connection not allowed by ruleset."""
REP_NETWORK_UNREACHABLE: int = 0x03
"""Network unreachable."""
REP_HOST_UNREACHABLE: int = 0x04
"""Host unreachable."""
REP_CONNECTION_REFUSED: int = 0x05
"""Connection refused."""
REP_TTL_EXPIRED: int = 0x06
"""TTL expired."""
REP_COMMAND_NOT_SUPPORTED: int = 0x07
"""Command not supported."""
REP_ADDRESS_TYPE_NOT_SUPPORTED: int = 0x08
"""Address type not supported."""

# --- Reserved / RSV ---
RSV: int = 0x00
"""Reserved byte (must be 0x00)."""


class SOCKS5Protocol:
    """SOCKS5 server protocol handler.

    Implements the server side of the SOCKS5 handshake:

    1. Read client greeting (version, auth methods).
    2. Select authentication method and reply.
    3. If username/password auth, perform RFC 1929 sub-negotiation.
    4. Read client request (command, address type, destination).
    5. Reply with success.

    Usage::

        protocol = SOCKS5Protocol()
        host, port = await protocol.negotiate(reader, writer)
        # Now establish the upstream connection to host:port

    Args:
        username: Optional username for RFC 1929 authentication.
            If ``None``, username/password auth is not offered.
        password: Optional password for RFC 1929 authentication.
    """

    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        self._username = username
        self._password = password

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def negotiate(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> tuple[str, int]:
        """Perform the full SOCKS5 handshake.

        1. Reads and processes the client greeting.
        2. Selects an authentication method.
        3. Performs authentication if required.
        4. Reads the client request and extracts the target ``(host, port)``.

        Args:
            reader: Client stream reader.
            writer: Client stream writer.

        Returns:
            Tuple of ``(target_host, target_port)`` that the client
            wants to connect to.

        Raises:
            ProxyProtocolError: If the SOCKS5 handshake fails at any
                stage (invalid version, unsupported command, etc.).
            asyncio.IncompleteReadError: If the connection is closed
                prematurely.
        """
        # ---- Step 1: Client greeting ----
        await self._read_greeting(reader)

        # ---- Step 2: Method selection ----
        await self._send_method_selection(writer)

        # ---- Step 3: Authentication (if needed) ----
        if self._username is not None and self._password is not None:
            await self._authenticate(reader, writer)

        # ---- Step 4: Client request ----
        host, port = await self._read_request(reader)

        # ---- Step 5: Send success reply ----
        await self._send_reply(writer, REP_SUCCESS, host, port)

        return host, port

    # ------------------------------------------------------------------
    # Internal: Greeting
    # ------------------------------------------------------------------

    async def _read_greeting(self, reader: asyncio.StreamReader) -> None:
        """Read and validate the SOCKS5 client greeting.

        Format::

            +----+----------+----------+
            |VER | NMETHODS | METHODS  |
            +----+----------+----------+
            | 1  |    1     | 1 to 255 |
            +----+----------+----------+

        Raises:
            ProxyProtocolError: If the version is not SOCKS5 or the
                greeting is malformed.
        """
        data = await reader.readexactly(2)
        ver, nmethods = struct.unpack("!BB", data)

        if ver != SOCKS_VERSION:
            raise ProxyProtocolError(
                f"Unsupported SOCKS version: {ver}. "
                f"Expected {SOCKS_VERSION} (SOCKS5).",
            )

        if nmethods == 0:
            raise ProxyProtocolError(
                "SOCKS5 greeting has no authentication methods.",
            )

        methods = await reader.readexactly(nmethods)
        self._client_methods = set(methods)
        logger.debug(
            "SOCKS5 greeting: version=%d, methods=%s",
            ver,
            [hex(m) for m in methods],
        )

    async def _send_method_selection(
        self,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Select and send the authentication method.

        Prefers ``NO AUTHENTICATION REQUIRED`` (0x00).  If username/
        password is configured, offers it as a fallback.

        Format::

            +----+--------+
            |VER | METHOD |
            +----+--------+
            | 1  |   1    |
            +----+--------+
        """
        method = self._select_method()
        writer.write(struct.pack("!BB", SOCKS_VERSION, method))
        await writer.drain()

        if method == AUTH_NO_ACCEPTABLE:
            raise ProxyProtocolError(
                "No acceptable SOCKS5 authentication method. "
                f"Client offered: {[hex(m) for m in self._client_methods]}",
            )

        logger.debug("SOCKS5 selected method: 0x%02x", method)

    def _select_method(self) -> int:
        """Select the best authentication method.

        Returns:
            The chosen method code.
        """
        # Prefer no authentication
        if AUTH_NONE in self._client_methods:
            return AUTH_NONE

        # Fall back to username/password if configured
        if (
            self._username is not None
            and self._password is not None
            and AUTH_USERNAME_PASSWORD in self._client_methods
        ):
            return AUTH_USERNAME_PASSWORD

        return AUTH_NO_ACCEPTABLE

    # ------------------------------------------------------------------
    # Internal: Username/Password Authentication (RFC 1929)
    # ------------------------------------------------------------------

    async def _authenticate(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Perform RFC 1929 username/password authentication.

        Format::

            +----+------+----------+------+----------+
            |VER | ULEN |  UNAME   | PLEN |  PASSWD  |
            +----+------+----------+------+----------+
            | 1  |  1   | 1 to 255 |  1   | 1 to 255 |
            +----+------+----------+------+----------+

        Raises:
            ProxyProtocolError: If authentication fails.
        """
        data = await reader.readexactly(2)
        ver, ulen = struct.unpack("!BB", data)

        if ver != 0x01:
            raise ProxyProtocolError(
                f"Invalid username/password auth version: {ver}",
            )

        uname = await reader.readexactly(ulen)
        plen_byte = await reader.readexactly(1)
        plen = plen_byte[0]
        passwd = await reader.readexactly(plen)

        username = uname.decode("utf-8", errors="replace")
        password = passwd.decode("utf-8", errors="replace")

        if username == self._username and password == self._password:
            # Success
            writer.write(struct.pack("!BB", 0x01, 0x00))
            await writer.drain()
            logger.debug("SOCKS5 username/password auth succeeded")
        else:
            # Failure
            writer.write(struct.pack("!BB", 0x01, 0x01))
            await writer.drain()
            raise ProxyProtocolError(
                "SOCKS5 username/password authentication failed",
            )

    # ------------------------------------------------------------------
    # Internal: Client Request
    # ------------------------------------------------------------------

    async def _read_request(
        self,
        reader: asyncio.StreamReader,
    ) -> tuple[str, int]:
        """Read and parse the SOCKS5 client request.

        Format::

            +----+-----+-------+------+----------+----------+
            |VER | CMD |  RSV  | ATYP | DST.ADDR | DST.PORT |
            +----+-----+-------+------+----------+----------+
            | 1  |  1  |   1   |  1   | Variable |    2     |
            +----+-----+-------+------+----------+----------+

        Args:
            reader: Client stream reader.

        Returns:
            Tuple of ``(target_host, target_port)``.

        Raises:
            ProxyProtocolError: If the command is not CONNECT or the
                address type is unsupported.
        """
        data = await reader.readexactly(4)
        ver, cmd, rsv, atyp = struct.unpack("!BBBB", data)

        if ver != SOCKS_VERSION:
            raise ProxyProtocolError(
                f"Unsupported SOCKS version in request: {ver}",
            )

        if cmd != CMD_CONNECT:
            raise ProxyProtocolError(
                f"Unsupported SOCKS5 command: {cmd}. "
                f"Only CONNECT (0x01) is supported.",
            )

        if rsv != RSV:
            logger.debug("SOCKS5 request RSV byte is non-zero: 0x%02x", rsv)

        host = await self._read_address(reader, atyp)
        port_bytes = await reader.readexactly(2)
        port = struct.unpack("!H", port_bytes)[0]

        logger.debug(
            "SOCKS5 request: cmd=CONNECT, atyp=%d, host=%s, port=%d",
            atyp,
            host,
            port,
        )

        return host, port

    async def _read_address(
        self,
        reader: asyncio.StreamReader,
        atyp: int,
    ) -> str:
        """Read the destination address based on address type.

        Args:
            reader: Client stream reader.
            atyp: Address type byte.

        Returns:
            Destination hostname or IP string.

        Raises:
            ProxyProtocolError: If the address type is unsupported.
        """
        if atyp == ATYP_IPV4:
            data = await reader.readexactly(4)
            return str(ipaddress.IPv4Address(data))

        if atyp == ATYP_DOMAINNAME:
            length_byte = await reader.readexactly(1)
            length = length_byte[0]
            if length == 0:
                raise ProxyProtocolError(
                    "SOCKS5 domain name has zero length.",
                )
            data = await reader.readexactly(length)
            return data.decode("ascii", errors="replace")

        if atyp == ATYP_IPV6:
            data = await reader.readexactly(16)
            return str(ipaddress.IPv6Address(data))

        raise ProxyProtocolError(
            f"Unsupported SOCKS5 address type: {atyp}. "
            f"Supported: IPv4 (0x01), DOMAINNAME (0x02), IPv6 (0x04).",
        )

    # ------------------------------------------------------------------
    # Internal: Reply
    # ------------------------------------------------------------------

    async def _send_reply(
        self,
        writer: asyncio.StreamWriter,
        rep: int,
        host: str,
        port: int,
    ) -> None:
        """Send a SOCKS5 reply to the client.

        Uses ``0.0.0.0`` and port ``0`` for the bound address since
        we don't need to report a different bind address (typical for
        simple forward proxies).

        Format::

            +----+-----+-------+------+----------+----------+
            |VER | REP |  RSV  | ATYP | BND.ADDR | BND.PORT |
            +----+-----+-------+------+----------+----------+
            | 1  |  1  |   1   |  1   | Variable |    2     |
            +----+-----+-------+------+----------+----------+

        Args:
            writer: Client stream writer.
            rep: Reply code.
            host: Bound host (for logging, not actually used).
            port: Bound port (for logging, not actually used).
        """
        # Use BND.ADDR = 0.0.0.0 (IPv4), BND.PORT = 0
        reply = struct.pack(
            "!BBBB4sH",
            SOCKS_VERSION,
            rep,
            RSV,
            ATYP_IPV4,
            b"\x00\x00\x00\x00",
            0,
        )
        writer.write(reply)
        await writer.drain()

        logger.debug(
            "SOCKS5 reply: rep=%d, bound=%s:%d",
            rep,
            host,
            port,
        )


# ------------------------------------------------------------------
# Convenience: Protocol detection
# ------------------------------------------------------------------

SOCKS5_FIRST_BYTE: int = 0x05
"""The first byte of a SOCKS5 greeting is always 0x05."""


async def peek_protocol(
    reader: asyncio.StreamReader,
) -> str:
    """Peek at the first byte to determine if this is SOCKS5 or HTTP.

    Reads one byte without consuming it from the stream, then decides
    based on the value:

    * ``0x05`` → ``"socks5"``
    * Anything else → ``"http"``

    Args:
        reader: Client stream reader.

    Returns:
        ``"socks5"`` or ``"http"``.

    Raises:
        ProxyProtocolError: If the connection is closed before any
            data is received.
    """
    try:
        byte = await reader.readexactly(1)
    except asyncio.IncompleteReadError as e:
        raise ProxyProtocolError(
            "Connection closed before protocol detection",
        ) from e

    # "Unget" the byte by prepending it.
    # Ensure _buffer stays a bytearray (Python 3.13+ StreamReader.read()
    # uses del self._buffer[:n] which fails on bytes).
    # type: ignore[attr-defined]
    reader._buffer = bytearray(byte) + reader._buffer

    if byte[0] == SOCKS5_FIRST_BYTE:
        return "socks5"

    return "http"
