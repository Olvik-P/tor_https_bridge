"""Tests for tor_https_bridge.utils.system."""

from __future__ import annotations

import asyncio
import signal
from unittest.mock import MagicMock, patch

from tor_https_bridge.utils.system import (
    get_platform_info,
    is_posix,
    is_windows,
    print_banner,
    setup_signal_handlers,
)


class TestGetPlatformInfo:
    """Tests for get_platform_info."""

    def test_returns_string(self) -> None:
        info = get_platform_info()
        assert isinstance(info, str)
        assert len(info) > 0


class TestIsWindows:
    """Tests for is_windows."""

    def test_returns_bool(self) -> None:
        result = is_windows()
        assert isinstance(result, bool)


class TestIsPosix:
    """Tests for is_posix."""

    def test_returns_bool(self) -> None:
        result = is_posix()
        assert isinstance(result, bool)

    def test_windows_not_posix(self) -> None:
        with patch("platform.system", return_value="Windows"):
            assert is_posix() is False

    def test_linux_is_posix(self) -> None:
        with patch("platform.system", return_value="Linux"):
            assert is_posix() is True

    def test_darwin_is_posix(self) -> None:
        with patch("platform.system", return_value="Darwin"):
            assert is_posix() is True


class TestSetupSignalHandlers:
    """Tests for setup_signal_handlers."""

    def test_on_windows_noop(self) -> None:
        loop = MagicMock(spec=asyncio.AbstractEventLoop)
        handler = MagicMock()

        with patch(
            "tor_https_bridge.utils.system.is_windows",
            return_value=True,
        ):
            setup_signal_handlers(loop, handler)

        loop.add_signal_handler.assert_not_called()

    def test_on_posix_registers_handlers(self) -> None:
        loop = MagicMock(spec=asyncio.AbstractEventLoop)
        handler = MagicMock()

        with patch(
            "tor_https_bridge.utils.system.is_windows",
            return_value=False,
        ):
            setup_signal_handlers(loop, handler)

        assert loop.add_signal_handler.call_count == 2
        loop.add_signal_handler.assert_any_call(signal.SIGTERM, handler)
        loop.add_signal_handler.assert_any_call(signal.SIGINT, handler)

    def test_on_posix_not_implemented_error(self) -> None:
        """Should silently ignore NotImplementedError."""
        loop = MagicMock(spec=asyncio.AbstractEventLoop)
        loop.add_signal_handler.side_effect = NotImplementedError()
        handler = MagicMock()

        with patch(
            "tor_https_bridge.utils.system.is_windows",
            return_value=False,
        ):
            # Should not raise
            setup_signal_handlers(loop, handler)

    def test_on_posix_value_error(self) -> None:
        """Should silently ignore ValueError."""
        loop = MagicMock(spec=asyncio.AbstractEventLoop)
        loop.add_signal_handler.side_effect = ValueError()
        handler = MagicMock()

        with patch(
            "tor_https_bridge.utils.system.is_windows",
            return_value=False,
        ):
            # Should not raise
            setup_signal_handlers(loop, handler)


class TestPrintBanner:
    """Tests for print_banner."""

    def test_print_banner_output(self, capsys) -> None:
        print_banner(
            https_host="127.0.0.1",
            https_port=3128,
            tor_host="127.0.0.1",
            tor_port=9050,
            buffer_size=8192,
            connect_timeout=30,
            read_timeout=60,
        )

        captured = capsys.readouterr()
        assert "Tor HTTPS Bridge Proxy" in captured.out
        assert "127.0.0.1:3128" in captured.out
        assert "9050" in captured.out
        assert "8192" in captured.out
        assert "30s" in captured.out
        assert "60s" in captured.out

    def test_print_banner_custom_values(self, capsys) -> None:
        print_banner(
            https_host="0.0.0.0",
            https_port=8080,
            tor_host="10.0.0.1",
            tor_port=9150,
            buffer_size=16384,
            connect_timeout=10,
            read_timeout=120,
        )

        captured = capsys.readouterr()
        assert "0.0.0.0:8080" in captured.out
        assert "10.0.0.1" in captured.out
        assert "9150" in captured.out
        assert "16384" in captured.out
        assert "10s" in captured.out
        assert "120s" in captured.out
