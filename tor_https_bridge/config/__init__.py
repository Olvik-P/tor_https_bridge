"""Configuration package for Tor HTTPS Bridge Proxy."""

from tor_https_bridge.config.constants import VERSION
from tor_https_bridge.config.settings import Settings, load_settings

__all__ = [
    "Settings",
    "load_settings",
    "VERSION",
]
