"""Core package — server, handler, forwarder, and exceptions."""

from tor_https_bridge.core.exceptions import (
    ConfigurationError,
    ProxyConnectionError,
    ProxyProtocolError,
    ProxyShutdownError,
    ProxyTimeoutError,
    TorBridgeError,
)
from tor_https_bridge.core.forwarder import DataForwarder
from tor_https_bridge.core.handler import ClientHandler
from tor_https_bridge.core.server import TorHTTPSProxy

__all__ = [
    "TorHTTPSProxy",
    "ClientHandler",
    "DataForwarder",
    "TorBridgeError",
    "ProxyProtocolError",
    "ProxyConnectionError",
    "ProxyTimeoutError",
    "ProxyShutdownError",
    "ConfigurationError",
]
