"""Tests for tor_https_bridge.protocol.http_parser."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from tor_https_bridge.core.exceptions import ProxyProtocolError
from tor_https_bridge.protocol.http_parser import HTTPConnectParser


class TestHTTPConnectParserReadRequest:
    """Tests for HTTPConnectParser.read_request."""

    @pytest.mark.asyncio
    async def test_read_valid_request(self) -> None:
        reader = AsyncMock(spec=asyncio.StreamReader)
        reader.read = AsyncMock(
            side_effect=[
                b"CONNECT example.com:443 HTTP/1.1\r\n",
                b"Host: example.com\r\n",
                b"\r\n",
            ],
        )

        result = await HTTPConnectParser.read_request(reader, max_size=65535)
        expected = (
            b"CONNECT example.com:443 HTTP/1.1\r\n"
            b"Host: example.com\r\n\r\n"
        )
        assert result == expected

    @pytest.mark.asyncio
    async def test_read_request_single_chunk(self) -> None:
        reader = AsyncMock(spec=asyncio.StreamReader)
        reader.read = AsyncMock(
            return_value=b"CONNECT example.com:443 HTTP/1.1\r\n\r\n",
        )

        result = await HTTPConnectParser.read_request(reader, max_size=65535)
        assert result == b"CONNECT example.com:443 HTTP/1.1\r\n\r\n"

    @pytest.mark.asyncio
    async def test_read_request_exceeds_max_size(self) -> None:
        reader = AsyncMock(spec=asyncio.StreamReader)
        # Return data that exceeds max_size (no CRLF_DOUBLE found)
        # First chunk: 60 bytes, remaining=40, reads min(1024, 40)=40
        # Second chunk: returns 50 bytes, total=110 > 100
        reader.read = AsyncMock(
            side_effect=[
                b"A" * 60,
                b"B" * 50,
            ],
        )

        with pytest.raises(ProxyProtocolError, match="exceeds"):
            await HTTPConnectParser.read_request(reader, max_size=100)

    @pytest.mark.asyncio
    async def test_read_request_connection_closed(self) -> None:
        reader = AsyncMock(spec=asyncio.StreamReader)
        reader.read = AsyncMock(return_value=b"")

        with pytest.raises(
            ProxyProtocolError,
            match="Connection closed before complete request",
        ):
            await HTTPConnectParser.read_request(reader, max_size=65535)

    @pytest.mark.asyncio
    async def test_read_request_empty_chunks_then_data(self) -> None:
        """Reader returns empty chunk before complete request."""
        reader = AsyncMock(spec=asyncio.StreamReader)
        reader.read = AsyncMock(
            side_effect=[
                b"",
            ],
        )

        with pytest.raises(ProxyProtocolError):
            await HTTPConnectParser.read_request(reader, max_size=65535)


class TestHTTPConnectParserParseConnect:
    """Tests for HTTPConnectParser.parse_connect."""

    def test_parse_valid_connect_with_port(self) -> None:
        data = b"CONNECT example.com:443 HTTP/1.1\r\nHost: example.com\r\n\r\n"
        host, port, method = HTTPConnectParser.parse_connect(data)
        assert host == "example.com"
        assert port == 443
        assert method == "CONNECT"

    def test_parse_valid_connect_without_port(self) -> None:
        """Should default to 443 when no port specified."""
        data = b"CONNECT example.com HTTP/1.1\r\n\r\n"
        host, port, method = HTTPConnectParser.parse_connect(data)
        assert host == "example.com"
        assert port == 443
        assert method == "CONNECT"

    def test_parse_valid_connect_ip_address(self) -> None:
        data = b"CONNECT 192.168.1.1:8080 HTTP/1.1\r\n\r\n"
        host, port, method = HTTPConnectParser.parse_connect(data)
        assert host == "192.168.1.1"
        assert port == 8080
        assert method == "CONNECT"

    def test_parse_valid_connect_ipv6(self) -> None:
        """IPv6 addresses in CONNECT are not natively supported by parser."""
        data = b"CONNECT [::1]:443 HTTP/1.1\r\n\r\n"
        with pytest.raises(ProxyProtocolError, match="Parse error"):
            HTTPConnectParser.parse_connect(data)

    def test_parse_get_request(self) -> None:
        """GET requests should be parsed successfully (not rejected)."""
        data = b"GET http://example.com HTTP/1.1\r\n\r\n"
        host, port, method = HTTPConnectParser.parse_connect(data)
        assert host == "example.com"
        assert port == 443
        assert method == "GET"

    def test_parse_get_request_with_port(self) -> None:
        data = b"GET http://example.com:8080/path HTTP/1.1\r\n\r\n"
        host, port, method = HTTPConnectParser.parse_connect(data)
        assert host == "example.com"
        assert port == 8080
        assert method == "GET"

    def test_parse_post_request(self) -> None:
        data = b"POST https://api.example.com:8443/data HTTP/1.1\r\n\r\n"
        host, port, method = HTTPConnectParser.parse_connect(data)
        assert host == "api.example.com"
        assert port == 8443
        assert method == "POST"

    def test_parse_empty_method(self) -> None:
        data = b"\r\n\r\n"
        with pytest.raises(ProxyProtocolError, match="Invalid method"):
            HTTPConnectParser.parse_connect(data)

    def test_parse_missing_host(self) -> None:
        data = b"CONNECT  HTTP/1.1\r\n\r\n"
        with pytest.raises(ProxyProtocolError, match="Invalid (host|method)"):
            HTTPConnectParser.parse_connect(data)

    def test_parse_host_too_long(self) -> None:
        long_host = "a" * 256
        data = f"CONNECT {long_host}:443 HTTP/1.1\r\n\r\n".encode()
        with pytest.raises(ProxyProtocolError, match="Invalid host"):
            HTTPConnectParser.parse_connect(data)

    def test_parse_invalid_port_non_numeric(self) -> None:
        data = b"CONNECT example.com:abc HTTP/1.1\r\n\r\n"
        with pytest.raises(ProxyProtocolError, match="Parse error"):
            HTTPConnectParser.parse_connect(data)

    def test_parse_port_too_low(self) -> None:
        data = b"CONNECT example.com:0 HTTP/1.1\r\n\r\n"
        with pytest.raises(ProxyProtocolError, match="Invalid port"):
            HTTPConnectParser.parse_connect(data)

    def test_parse_port_too_high(self) -> None:
        data = b"CONNECT example.com:65536 HTTP/1.1\r\n\r\n"
        with pytest.raises(ProxyProtocolError, match="Invalid port"):
            HTTPConnectParser.parse_connect(data)

    def test_parse_non_ascii_encoding(self) -> None:
        data = "CONNECT éxample.com:443 HTTP/1.1\r\n\r\n".encode("latin-1")
        with pytest.raises(ProxyProtocolError, match="Parse error"):
            HTTPConnectParser.parse_connect(data)

    def test_parse_extra_headers(self) -> None:
        data = (
            b"CONNECT example.com:443 HTTP/1.1\r\n"
            b"Host: example.com\r\n"
            b"User-Agent: Mozilla/5.0\r\n"
            b"Proxy-Authorization: Basic dGVzdDp0ZXN0\r\n"
            b"\r\n"
        )
        host, port, method = HTTPConnectParser.parse_connect(data)
        assert host == "example.com"
        assert port == 443
        assert method == "CONNECT"

    def test_parse_min_port_boundary(self) -> None:
        data = b"CONNECT example.com:1 HTTP/1.1\r\n\r\n"
        host, port, method = HTTPConnectParser.parse_connect(data)
        assert host == "example.com"
        assert port == 1
        assert method == "CONNECT"

    def test_parse_max_port_boundary(self) -> None:
        data = b"CONNECT example.com:65535 HTTP/1.1\r\n\r\n"
        host, port, method = HTTPConnectParser.parse_connect(data)
        assert host == "example.com"
        assert port == 65535
        assert method == "CONNECT"


class TestHTTPConnectParserIntegration:
    """Integration tests for HTTPConnectParser."""

    @pytest.mark.asyncio
    async def test_read_and_parse(self) -> None:
        reader = AsyncMock(spec=asyncio.StreamReader)
        reader.read = AsyncMock(
            return_value=b"CONNECT example.com:443 HTTP/1.1\r\n\r\n",
        )

        raw = await HTTPConnectParser.read_request(reader, max_size=65535)
        host, port, method = HTTPConnectParser.parse_connect(raw)
        assert host == "example.com"
        assert port == 443
        assert method == "CONNECT"

    @pytest.mark.asyncio
    async def test_read_and_parse_without_port(self) -> None:
        reader = AsyncMock(spec=asyncio.StreamReader)
        reader.read = AsyncMock(
            return_value=b"CONNECT example.com HTTP/1.1\r\n\r\n",
        )

        raw = await HTTPConnectParser.read_request(reader, max_size=65535)
        host, port, method = HTTPConnectParser.parse_connect(raw)
        assert host == "example.com"
        assert port == 443
        assert method == "CONNECT"
