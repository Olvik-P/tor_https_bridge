"""HTTP CONNECT method parser for HTTPS proxy requests."""

from __future__ import annotations

import asyncio
import logging
from typing import Protocol

from tor_https_bridge.config.constants import (
    CHUNK_READ_SIZE,
    CRLF_DOUBLE,
    DEFAULT_HTTPS_PORT,
    HTTP_METHOD_CONNECT,
    MAX_HOSTNAME_LENGTH,
    MAX_PORT,
    MIN_PORT,
)
from tor_https_bridge.core.exceptions import ProxyProtocolError

logger = logging.getLogger(__name__)


class HTTPConnectParserProtocol(Protocol):
    """Protocol for HTTP CONNECT parser implementations."""

    async def read_request(
        self,
        reader: asyncio.StreamReader,
        max_size: int,
    ) -> bytes:
        """Read HTTP request until double CRLF.

        Args:
            reader: Stream reader to read from.
            max_size: Maximum allowed request size in bytes.

        Returns:
            Raw HTTP request bytes.

        Raises:
            ProxyProtocolError: If the request exceeds *max_size* or
                the connection is closed prematurely.
        """
        ...

    def parse_connect(self, data: bytes) -> tuple[str, int, str]:
        """Parse HTTP request and return ``(host, port, method)``.

        Args:
            data: Raw HTTP request bytes.

        Returns:
            Tuple of ``(hostname, port, method)``.

        Raises:
            ProxyProtocolError: If the request is malformed.
        """
        ...


class HTTPConnectParser:
    """Parser for HTTP CONNECT method requests.

    Reads and validates HTTP CONNECT requests from clients, extracting
    the target hostname and port for upstream connection.

    Usage::

        parser = HTTPConnectParser()
        raw = await parser.read_request(reader, max_size=65535)
        host, port = parser.parse_connect(raw)
    """

    @staticmethod
    async def read_request(
        reader: asyncio.StreamReader,
        max_size: int,
        timeout: float | None = None,
    ) -> bytes:
        """Read HTTP request until double CRLF.

        Args:
            reader: Stream reader to read from.
            max_size: Maximum allowed request size in bytes.
            timeout: Optional timeout in seconds for reading the request.
                If None, no timeout is applied.

        Returns:
            Raw HTTP request bytes.

        Raises:
            ProxyProtocolError: If the request exceeds *max_size* or
                the connection is closed prematurely.
            asyncio.TimeoutError: If *timeout* seconds elapse before
                the full request is received.
        """
        data = bytearray()
        while CRLF_DOUBLE not in data:
            remaining = max_size - len(data)
            read_size = min(CHUNK_READ_SIZE, remaining)
            if timeout is not None:
                chunk = await asyncio.wait_for(
                    reader.read(read_size),
                    timeout=timeout,
                )
            else:
                chunk = await reader.read(read_size)
            if not chunk:
                raise ProxyProtocolError(
                    "Connection closed before complete request",
                )
            data.extend(chunk)
            if len(data) > max_size:
                raise ProxyProtocolError(
                    f"Request exceeds {max_size} bytes",
                )
        return bytes(data)

    @staticmethod
    def _parse_port(port_str: str, context: str = "") -> int:
        """Parse and validate a port string.

        Args:
            port_str: String representation of the port.
            context: Optional context for error messages.

        Returns:
            Parsed integer port.

        Raises:
            ProxyProtocolError: If the port string is not a valid integer
                or is out of range.
        """
        try:
            port = int(port_str)
        except ValueError as e:
            raise ProxyProtocolError(
                f"Parse error: invalid port {context!r}: {e}",
            ) from e
        return port

    @staticmethod
    def parse_connect(data: bytes) -> tuple[str, int, str]:
        """Parse HTTP request and return ``(host, port, method)``.

        Supports both CONNECT requests (``CONNECT host:port HTTP/1.1``)
        and plain HTTP proxy requests (``GET http://host/path HTTP/1.1``).

        Args:
            data: Raw HTTP request bytes.

        Returns:
            Tuple of ``(hostname, port, method)``.

        Raises:
            ProxyProtocolError: If the request is malformed — invalid
                method, missing host, invalid port, or encoding errors.
        """
        try:
            first_line = data.split(b"\r\n")[0].decode("ascii")
            parts = first_line.split()

            if len(parts) < 3:
                method = parts[0] if parts else "None"
                raise ProxyProtocolError(f"Invalid method: {method}")

            method = parts[0]

            if method == HTTP_METHOD_CONNECT:
                # CONNECT host:port HTTP/1.1
                host_port = parts[1].split(":")
                host = host_port[0]
                if len(host_port) > 1:
                    port = HTTPConnectParser._parse_port(
                        host_port[1],
                        context=host_port[1],
                    )
                else:
                    port = DEFAULT_HTTPS_PORT
            else:
                # GET http://host:port/path HTTP/1.1
                url = parts[1]
                # Strip protocol prefix
                if url.startswith("http://"):
                    url = url[7:]
                elif url.startswith("https://"):
                    url = url[8:]

                # Split host:port/path
                host_port = url.split(":")
                host = host_port[0]
                if "/" in host:
                    host = host.split("/")[0]

                if len(host_port) > 1:
                    rest = host_port[1]
                    if "/" in rest:
                        port = HTTPConnectParser._parse_port(
                            rest.split("/")[0],
                            context=rest,
                        )
                    else:
                        port = HTTPConnectParser._parse_port(
                            rest,
                            context=rest,
                        )
                else:
                    port = DEFAULT_HTTPS_PORT

            if not host or len(host) > MAX_HOSTNAME_LENGTH:
                raise ProxyProtocolError(f"Invalid host: {host}")

            if not (MIN_PORT <= port <= MAX_PORT):
                raise ProxyProtocolError(f"Invalid port: {port}")

            return host, port, method

        except (UnicodeDecodeError, ValueError, IndexError) as e:
            raise ProxyProtocolError(f"Parse error: {e}") from e
