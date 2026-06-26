"""Tor HTTPS Bridge Proxy.

Transparently forwards HTTPS CONNECT and SOCKS5 proxy traffic to Tor
SOCKS5.

A production-ready Python package that listens for HTTPS CONNECT proxy
requests and/or SOCKS5 connections, automatically detects the protocol,
and tunnels them through the Tor SOCKS5 proxy, providing anonymous
browsing for any application.

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
