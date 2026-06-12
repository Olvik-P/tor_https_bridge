"""Protocol package — HTTP parser and SOCKS5 adapter."""

from tor_https_bridge.protocol.http_parser import HTTPConnectParser
from tor_https_bridge.protocol.socks_adapter import TorConnector

__all__ = [
    "HTTPConnectParser",
    "TorConnector",
]
