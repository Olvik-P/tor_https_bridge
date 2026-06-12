"""Tor HTTPS Bridge Proxy.

Transparently forwards HTTPS proxy traffic to Tor SOCKS5.

A production-ready Python package that listens for HTTPS CONNECT proxy
requests and tunnels them through the Tor SOCKS5 proxy, providing
anonymous browsing for any application configured to use an HTTP(S)
proxy.

Usage::

    # As a CLI tool
    tor-https-bridge

    # As a Python module
    python -m tor_https_bridge

    # Programmatic usage
    from tor_https_bridge import TorHTTPSProxy
    from tor_https_bridge.config.settings import Settings

    settings = Settings()
    proxy = TorHTTPSProxy(settings)
    await proxy.start()
"""

from __future__ import annotations

from tor_https_bridge.config.constants import VERSION
from tor_https_bridge.core.server import TorHTTPSProxy

__all__ = [
    "TorHTTPSProxy",
    "VERSION",
]

__version__ = VERSION
