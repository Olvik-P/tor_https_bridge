"""System utilities for Tor HTTPS Bridge Proxy."""

from __future__ import annotations

import platform
import signal

# Константы для рисования рамок банера (Box Drawing characters)
_TOP_LEFT = "\u2554"
_TOP_RIGHT = "\u2557"
_BOTTOM_LEFT = "\u255a"
_BOTTOM_RIGHT = "\u255d"
_HORIZ = "\u2550"
_VERT = "\u2551"
# Ширина рамки (расчитайте один раз)
_WIDTH = 79  # Максимальная ширина строки


def get_platform_info() -> str:
    """Return a human-readable platform identification string.

    Returns:
        Platform info (e.g. ``Windows-10-10.0.19041-SP0``).
    """
    return platform.platform()


def is_windows() -> bool:
    """Check if the current OS is Windows.

    Returns:
        ``True`` if running on Windows.
    """
    return platform.system() == "Windows"


def is_posix() -> bool:
    """Check if the current OS is POSIX-compliant (Linux/macOS).

    Returns:
        ``True`` if running on a POSIX system.
    """
    return platform.system() in ("Linux", "Darwin")


def setup_signal_handlers(
    loop,
    handler: callable,
) -> None:
    """Register signal handlers for graceful shutdown.

    On POSIX systems, registers handlers for ``SIGTERM`` and ``SIGINT``.
    On Windows, signal handlers are not supported by the event loop,
    so this is a no-op (use ``KeyboardInterrupt`` handling instead).

    Usage::

        import asyncio
        loop = asyncio.get_running_loop()
        setup_signal_handlers(
            loop,
            lambda: asyncio.create_task(proxy.stop()),
        )

    Args:
        loop: The running asyncio event loop.
        handler: Callback to invoke on signal (typically schedules
            :meth:`TorHTTPSProxy.stop`).
    """
    if is_windows():
        return

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, handler)
        except (NotImplementedError, ValueError):
            pass


def print_banner(
    https_host: str,
    https_port: int,
    tor_host: str,
    tor_port: int,
    buffer_size: int,
    connect_timeout: int,
    read_timeout: int,
    sanitize_headers: bool = False,
    socks_host: str | None = None,
    socks_port: int | None = None,
) -> None:
    """Print startup banner with configuration summary.

    Args:
        https_host: HTTPS proxy listen host.
        https_port: HTTPS proxy listen port.
        tor_host: Tor SOCKS5 host.
        tor_port: Tor SOCKS5 port.
        buffer_size: Buffer size in bytes.
        connect_timeout: Connection timeout in seconds.
        read_timeout: Read timeout in seconds.
        sanitize_headers: Whether header sanitization is enabled.
        socks_host: SOCKS5 proxy listen host (if enabled).
        socks_port: SOCKS5 proxy listen port (if enabled).
    """
    stealth_status = "ON (headers sanitized)" if sanitize_headers else "OFF"

    listen_parts = [f"HTTPS {https_host}:{https_port}"]
    if socks_host is not None and socks_port is not None:
        listen_parts.append(f"SOCKS5 {socks_host}:{socks_port}")
    listen_str = ", ".join(listen_parts)

    # Собираем баннер из частей
    banner_lines = [
        f"{_TOP_LEFT}{_HORIZ * (_WIDTH - 2)}{_TOP_RIGHT}",
        f"{_VERT}{' ' * 18}🔒 Tor HTTPS Bridge Proxy{' ' * 34}{_VERT}",
        f"{_VERT}  Listen:     {listen_str:<55}{' ' * 8}{_VERT}",
        f"{_VERT}  Backend:    SOCKS5 {tor_host}:{tor_port:<36}"
        f"{' ' * 10}{_VERT}",
        f"{_VERT}  Buffer:     {buffer_size} bytes{' ' * 53}{_VERT}",
        f"{_VERT}  Timeout:    {connect_timeout}s (connect), "
        f"{read_timeout}s (read){' ' * 37}{_VERT}",
        f"{_VERT}  Stealth:    {stealth_status:<49}{' ' * 14}{_VERT}",
        f"{_VERT}  Configure:  HTTP proxy http://{https_host}:{https_port}"
        f"{' ' * 33}{_VERT}",
        f"{_VERT}              SOCKS5 proxy "
        f"{socks_host or https_host}:{socks_port or https_port}"
        f"{' ' * 38}{_VERT}",
        f"{_VERT}  Press Ctrl+C to stop{' ' * 55}{_VERT}",
        f"{_BOTTOM_LEFT}{_HORIZ * (_WIDTH - 2)}{_BOTTOM_RIGHT}",
    ]

    banner = "\n".join(banner_lines)
    print(banner)
