"""Custom exception hierarchy for Tor HTTPS Bridge Proxy.

All exceptions inherit from :class:`TorBridgeError` base class.
"""

from __future__ import annotations


class TorBridgeError(Exception):
    """Base exception for all Tor Bridge errors."""


class ProxyProtocolError(TorBridgeError):
    """Protocol violation from client (malformed HTTP CONNECT request)."""


class ProxyConnectionError(TorBridgeError):
    """Error connecting to upstream (Tor SOCKS5) destination."""


class ProxyTimeoutError(TorBridgeError):
    """Operation timed out (connect or read timeout)."""


class ProxyShutdownError(TorBridgeError):
    """Error during server shutdown."""


class ConfigurationError(TorBridgeError):
    """Invalid or missing configuration."""
