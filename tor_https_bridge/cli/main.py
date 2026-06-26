"""CLI entry point for Tor HTTPS Bridge Proxy.

Provides the ``tor-https-bridge`` console script entry point.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from tor_https_bridge.config.settings import Settings, load_settings
from tor_https_bridge.core.server import TorHTTPSProxy
from tor_https_bridge.utils.logging import setup_logging
from tor_https_bridge.utils.system import (
    print_banner,
    setup_signal_handlers,
)

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser.

    Returns:
        Configured argument parser.
    """
    parser = argparse.ArgumentParser(
        prog="tor-https-bridge",
        description=(
            "Transparently forwards HTTPS proxy and SOCKS5 traffic "
            "to Tor SOCKS5."
        ),
        epilog=(
            "Example: tor-https-bridge --proxy-port 8080 --tor-port 9150"
        ),
    )

    # HTTPS Proxy settings
    proxy_group = parser.add_argument_group("HTTPS Proxy")
    proxy_group.add_argument(
        "--proxy-host",
        default=None,
        help="HTTPS proxy listen host (default: 0.0.0.0)",
    )
    proxy_group.add_argument(
        "--proxy-port",
        type=int,
        default=None,
        help="HTTPS proxy listen port (default: 3128)",
    )
    proxy_group.add_argument(
        "--no-https-proxy",
        action="store_true",
        default=None,
        help="Disable the HTTPS CONNECT proxy",
    )

    # SOCKS5 Proxy settings (incoming)
    socks_group = parser.add_argument_group("SOCKS5 Proxy (incoming)")
    socks_group.add_argument(
        "--socks-host",
        default=None,
        help="SOCKS5 proxy listen host (default: 0.0.0.0)",
    )
    socks_group.add_argument(
        "--socks-port",
        type=int,
        default=None,
        help="SOCKS5 proxy listen port (default: 1080)",
    )
    socks_group.add_argument(
        "--no-socks-proxy",
        action="store_true",
        default=None,
        help="Disable the SOCKS5 proxy",
    )
    socks_group.add_argument(
        "--socks-username",
        default=None,
        help="SOCKS5 username for RFC 1929 auth (default: no auth)",
    )
    socks_group.add_argument(
        "--socks-password",
        default=None,
        help="SOCKS5 password for RFC 1929 auth",
    )

    # Tor settings
    tor_group = parser.add_argument_group("Tor SOCKS5 (backend)")
    tor_group.add_argument(
        "--tor-host",
        default=None,
        help="Tor SOCKS5 host (default: 127.0.0.1)",
    )
    tor_group.add_argument(
        "--tor-port",
        type=int,
        default=None,
        help="Tor SOCKS5 port (default: 9050)",
    )

    # Performance
    perf_group = parser.add_argument_group("Performance")
    perf_group.add_argument(
        "--buffer-size",
        type=int,
        default=None,
        help="Buffer size in bytes (default: 8192)",
    )
    perf_group.add_argument(
        "--backlog",
        type=int,
        default=None,
        help="Maximum pending connections (default: 100)",
    )

    # Timeouts
    timeout_group = parser.add_argument_group("Timeouts")
    timeout_group.add_argument(
        "--connect-timeout",
        type=int,
        default=None,
        help="Connection timeout in seconds (default: 60)",
    )
    timeout_group.add_argument(
        "--read-timeout",
        type=int,
        default=None,
        help="Read timeout in seconds (default: 120)",
    )

    # Logging
    parser.add_argument(
        "--log-level",
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level (default: INFO)",
    )

    # Config file
    parser.add_argument(
        "--config",
        default=None,
        help="Path to JSON/YAML config file",
    )

    # Version
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version and exit",
    )

    return parser


def _apply_cli_overrides(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
) -> dict:
    """Convert CLI args to settings overrides dict.

    Args:
        parser: Argument parser (for error formatting).
        args: Parsed CLI arguments.

    Returns:
        Dict of settings overrides.
    """
    overrides: dict = {}

    arg_to_setting = {
        "proxy_host": "https_proxy_host",
        "proxy_port": "https_proxy_port",
        "tor_host": "tor_socks_host",
        "tor_port": "tor_socks_port",
        "buffer_size": "buffer_size",
        "backlog": "backlog",
        "connect_timeout": "connect_timeout",
        "read_timeout": "read_timeout",
        "log_level": "log_level",
        "config": "config_file",
        "socks_host": "socks_proxy_host",
        "socks_port": "socks_proxy_port",
        "socks_username": "socks_proxy_username",
        "socks_password": "socks_proxy_password",
    }

    for arg_name, setting_name in arg_to_setting.items():
        value = getattr(args, arg_name, None)
        if value is not None:
            overrides[setting_name] = value

    # Handle boolean flags
    if getattr(args, "no_https_proxy", None) is True:
        overrides["https_proxy_enabled"] = False
    if getattr(args, "no_socks_proxy", None) is True:
        overrides["socks_proxy_enabled"] = False

    return overrides


async def async_main(settings: Settings) -> None:
    """Async main entry point.

    Args:
        settings: Resolved application settings.
    """
    setup_logging(level=settings.log_level)

    print_banner(
        https_host=settings.https_proxy_host,
        https_port=settings.https_proxy_port,
        tor_host=settings.tor_socks_host,
        tor_port=settings.tor_socks_port,
        buffer_size=settings.buffer_size,
        connect_timeout=settings.connect_timeout,
        read_timeout=settings.read_timeout,
        sanitize_headers=settings.sanitize_headers,
        socks_host=(
            settings.socks_proxy_host
            if settings.socks_proxy_enabled
            else None
        ),
        socks_port=(
            settings.socks_proxy_port
            if settings.socks_proxy_enabled
            else None
        ),
    )

    proxy = TorHTTPSProxy(settings)

    loop = asyncio.get_running_loop()

    def _signal_handler() -> None:
        # Use call_soon_threadsafe to schedule stop() on the event loop
        # from the signal handler (which runs in a different context).
        loop.call_soon_threadsafe(
            lambda: asyncio.create_task(proxy.stop()),
        )

    setup_signal_handlers(loop, _signal_handler)

    try:
        await proxy.start()
    except asyncio.CancelledError:
        pass
    finally:
        await proxy.stop()


def main() -> None:
    """CLI entry point.

    Parses arguments, loads settings, and starts the proxy server.
    """
    parser = build_parser()
    args = parser.parse_args()

    if args.version:
        from tor_https_bridge.config.constants import VERSION

        print(f"tor-https-bridge v{VERSION}")
        sys.exit(0)

    # Load settings with CLI overrides
    cli_overrides = _apply_cli_overrides(parser, args)
    settings = load_settings()

    if cli_overrides:
        settings = Settings(**{**settings.model_dump(), **cli_overrides})

    try:
        asyncio.run(async_main(settings))
    except KeyboardInterrupt:
        print("\n\U0001f6d1 Shutdown complete.")
        sys.exit(0)


if __name__ == "__main__":
    main()
