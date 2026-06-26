"""Package-wide constants for Tor HTTPS Bridge Proxy.

All magic numbers, default ports, buffer sizes, and timeouts
are defined here as UPPER_SNAKE_CASE named constants.
"""

from typing import Final

# ============================================================================
# Network
# ============================================================================

TOR_SOCKS_DEFAULT_HOST: Final[str] = "127.0.0.1"
"""Default Tor SOCKS5 host address."""

TOR_SOCKS_DEFAULT_PORT: Final[int] = 9050
"""Default Tor SOCKS5 port."""

SOCKS_PROXY_DEFAULT_HOST: Final[str] = "0.0.0.0"
"""Default SOCKS5 proxy listen host (all interfaces)."""

SOCKS_PROXY_DEFAULT_PORT: Final[int] = 1080
"""Default SOCKS5 proxy listen port."""

HTTPS_PROXY_DEFAULT_HOST: Final[str] = "0.0.0.0"
"""Default HTTPS proxy listen host (all interfaces)."""

HTTPS_PROXY_DEFAULT_PORT: Final[int] = 3128
"""Default HTTPS proxy listen port."""

BACKLOG_SIZE: Final[int] = 100
"""Maximum number of pending connections."""

# ============================================================================
# Buffer
# ============================================================================

BUFFER_SIZE: Final[int] = 8192
"""Default buffer size for data forwarding (bytes)."""

BUFFER_MULTIPLIER: Final[int] = 2
"""Multiplier for stream reader limit relative to buffer size."""

MAX_REQUEST_SIZE: Final[int] = 65535
"""Maximum allowed HTTP CONNECT request size (bytes)."""

CHUNK_READ_SIZE: Final[int] = 1024
"""Chunk size for reading HTTP request headers (bytes)."""

# ============================================================================
# Timeouts
# ============================================================================

CONNECT_TIMEOUT: Final[int] = 60
"""Timeout for establishing upstream SOCKS5 connection (seconds).

Increased from 30s to 60s because Tor circuit building can be slow,
especially when using bridges or when the network is congested.
"""

READ_TIMEOUT: Final[int] = 120
"""Timeout for reading from upstream connection (seconds).

Increased from 60s to 120s to accommodate slow Tor circuits.
"""

SHUTDOWN_TIMEOUT: Final[int] = 10
"""Timeout for graceful shutdown of active connections (seconds)."""

SOCKS_RETRY_COUNT: Final[int] = 2
"""Number of retry attempts for SOCKS5 connection failures."""

SOCKS_RETRY_DELAY: Final[float] = 2.0
"""Delay in seconds between SOCKS5 connection retry attempts."""

# ============================================================================
# HTTP
# ============================================================================

HTTP_200_CONNECTED: Final[bytes] = (
    b"HTTP/1.1 200 Connection established\r\n\r\n"
)
"""HTTP 200 response for successful CONNECT tunnel."""

HTTP_400_BAD_REQUEST: Final[bytes] = b"HTTP/1.1 400 Bad Request\r\n\r\n"
"""HTTP 400 response for malformed requests."""

HTTP_502_BAD_GATEWAY: Final[bytes] = b"HTTP/1.1 502 Bad Gateway\r\n\r\n"
"""HTTP 502 response for upstream connection failure."""

HTTP_METHOD_CONNECT: Final[str] = "CONNECT"
"""HTTP CONNECT method string."""

CRLF_DOUBLE: Final[bytes] = b"\r\n\r\n"
"""Double CRLF delimiter marking end of HTTP headers."""

CRLF: Final[bytes] = b"\r\n"
"""CRLF delimiter."""

# ============================================================================
# Limits
# ============================================================================

MAX_HOSTNAME_LENGTH: Final[int] = 255
"""Maximum valid hostname length (RFC 1035)."""

MIN_PORT: Final[int] = 1
"""Minimum valid port number."""

MAX_PORT: Final[int] = 65535
"""Maximum valid port number."""

DEFAULT_HTTPS_PORT: Final[int] = 443
"""Default HTTPS port when not specified in CONNECT request."""

# ============================================================================
# Stealth Mode (Header Sanitization)
# ============================================================================

SANITIZE_HEADERS_DEFAULT: Final[bool] = False
"""Default value for header sanitization (disabled by default for
backward compatibility)."""

DEFAULT_USER_AGENT: Final[str] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)
"""Default neutral User-Agent for sanitized requests."""

DEFAULT_ACCEPT_LANGUAGE: Final[str] = "en-US,en;q=0.9"
"""Default Accept-Language for sanitized requests."""

# ============================================================================
# Logging
# ============================================================================

LOG_FORMAT: Final[str] = "%(asctime)s | %(levelname)-8s | %(message)s"
"""Log message format string."""

LOG_DATE_FORMAT: Final[str] = "%H:%M:%S"
"""Log date format string."""

# ============================================================================
# Package
# ============================================================================

VERSION: Final[str] = "1.0.0"
"""Package version."""

PACKAGE_NAME: Final[str] = "tor-https-bridge"
"""Package name for CLI entry point."""

ENV_PREFIX: Final[str] = "TOR_BRIDGE_"
"""Environment variable prefix for configuration."""
