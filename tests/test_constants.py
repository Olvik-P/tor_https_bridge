"""Tests for tor_https_bridge.config.constants."""

from __future__ import annotations

from tor_https_bridge.config.constants import (
    BACKLOG_SIZE,
    BUFFER_MULTIPLIER,
    BUFFER_SIZE,
    CHUNK_READ_SIZE,
    CONNECT_TIMEOUT,
    CRLF,
    CRLF_DOUBLE,
    DEFAULT_HTTPS_PORT,
    ENV_PREFIX,
    HTTP_200_CONNECTED,
    HTTP_400_BAD_REQUEST,
    HTTP_502_BAD_GATEWAY,
    HTTP_METHOD_CONNECT,
    HTTPS_PROXY_DEFAULT_HOST,
    HTTPS_PROXY_DEFAULT_PORT,
    LOG_DATE_FORMAT,
    LOG_FORMAT,
    MAX_HOSTNAME_LENGTH,
    MAX_PORT,
    MAX_REQUEST_SIZE,
    MIN_PORT,
    PACKAGE_NAME,
    READ_TIMEOUT,
    SHUTDOWN_TIMEOUT,
    TOR_SOCKS_DEFAULT_HOST,
    TOR_SOCKS_DEFAULT_PORT,
    VERSION,
)


class TestNetworkConstants:
    """Tests for network-related constants."""

    def test_tor_socks_default_host(self) -> None:
        assert TOR_SOCKS_DEFAULT_HOST == "127.0.0.1"

    def test_tor_socks_default_port(self) -> None:
        assert TOR_SOCKS_DEFAULT_PORT == 9050

    def test_https_proxy_default_host(self) -> None:
        assert HTTPS_PROXY_DEFAULT_HOST == "0.0.0.0"

    def test_https_proxy_default_port(self) -> None:
        assert HTTPS_PROXY_DEFAULT_PORT == 3128

    def test_backlog_size(self) -> None:
        assert BACKLOG_SIZE == 100


class TestBufferConstants:
    """Tests for buffer-related constants."""

    def test_buffer_size(self) -> None:
        assert BUFFER_SIZE == 8192

    def test_buffer_multiplier(self) -> None:
        assert BUFFER_MULTIPLIER == 2

    def test_max_request_size(self) -> None:
        assert MAX_REQUEST_SIZE == 65535

    def test_chunk_read_size(self) -> None:
        assert CHUNK_READ_SIZE == 1024


class TestTimeoutConstants:
    """Tests for timeout-related constants."""

    def test_connect_timeout(self) -> None:
        assert CONNECT_TIMEOUT == 60

    def test_read_timeout(self) -> None:
        assert READ_TIMEOUT == 120

    def test_shutdown_timeout(self) -> None:
        assert SHUTDOWN_TIMEOUT == 10


class TestHTTPConstants:
    """Tests for HTTP-related constants."""

    def test_http_200_connected(self) -> None:
        expected = b"HTTP/1.1 200 Connection established\r\n\r\n"
        assert HTTP_200_CONNECTED == expected

    def test_http_400_bad_request(self) -> None:
        assert HTTP_400_BAD_REQUEST == b"HTTP/1.1 400 Bad Request\r\n\r\n"

    def test_http_502_bad_gateway(self) -> None:
        assert HTTP_502_BAD_GATEWAY == b"HTTP/1.1 502 Bad Gateway\r\n\r\n"

    def test_http_method_connect(self) -> None:
        assert HTTP_METHOD_CONNECT == "CONNECT"

    def test_crlf_double(self) -> None:
        assert CRLF_DOUBLE == b"\r\n\r\n"

    def test_crlf(self) -> None:
        assert CRLF == b"\r\n"


class TestLimitConstants:
    """Tests for limit-related constants."""

    def test_max_hostname_length(self) -> None:
        assert MAX_HOSTNAME_LENGTH == 255

    def test_min_port(self) -> None:
        assert MIN_PORT == 1

    def test_max_port(self) -> None:
        assert MAX_PORT == 65535

    def test_default_https_port(self) -> None:
        assert DEFAULT_HTTPS_PORT == 443


class TestLoggingConstants:
    """Tests for logging-related constants."""

    def test_log_format(self) -> None:
        assert LOG_FORMAT == "%(asctime)s | %(levelname)-8s | %(message)s"

    def test_log_date_format(self) -> None:
        assert LOG_DATE_FORMAT == "%H:%M:%S"


class TestPackageConstants:
    """Tests for package-related constants."""

    def test_version(self) -> None:
        assert VERSION == "1.0.0"

    def test_package_name(self) -> None:
        assert PACKAGE_NAME == "tor-https-bridge"

    def test_env_prefix(self) -> None:
        assert ENV_PREFIX == "TOR_BRIDGE_"


class TestStealthConstants:
    """Tests for stealth mode constants."""

    def test_sanitize_headers_default(self) -> None:
        from tor_https_bridge.config.constants import SANITIZE_HEADERS_DEFAULT

        assert SANITIZE_HEADERS_DEFAULT is False

    def test_default_user_agent(self) -> None:
        from tor_https_bridge.config.constants import DEFAULT_USER_AGENT

        assert isinstance(DEFAULT_USER_AGENT, str)
        assert len(DEFAULT_USER_AGENT) > 20
        assert "Chrome" in DEFAULT_USER_AGENT
        assert "Windows" in DEFAULT_USER_AGENT

    def test_default_accept_language(self) -> None:
        from tor_https_bridge.config.constants import DEFAULT_ACCEPT_LANGUAGE

        assert isinstance(DEFAULT_ACCEPT_LANGUAGE, str)
        assert DEFAULT_ACCEPT_LANGUAGE == "en-US,en;q=0.9"


class TestConstantsImmutability:
    """Verify constants have correct types."""

    def test_all_constants_are_typed_final(self) -> None:
        """Verify constants have correct types."""
        assert isinstance(TOR_SOCKS_DEFAULT_HOST, str)
        assert isinstance(TOR_SOCKS_DEFAULT_PORT, int)
        assert isinstance(BACKLOG_SIZE, int)
        assert isinstance(BUFFER_SIZE, int)
        assert isinstance(HTTP_200_CONNECTED, bytes)
        assert isinstance(VERSION, str)
        assert isinstance(ENV_PREFIX, str)
        assert isinstance(CRLF, bytes)
        assert isinstance(CRLF_DOUBLE, bytes)
        assert isinstance(LOG_FORMAT, str)
        assert isinstance(LOG_DATE_FORMAT, str)
