"""Tests for tor_https_bridge.cli.main."""

from __future__ import annotations

import argparse
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from tor_https_bridge.cli.main import (
    _apply_cli_overrides,
    async_main,
    build_parser,
    main,
)


class TestBuildParser:
    """Tests for build_parser."""

    def test_parser_created(self) -> None:
        parser = build_parser()
        assert isinstance(parser, argparse.ArgumentParser)
        assert parser.prog == "tor-https-bridge"

    def test_parser_has_proxy_group(self) -> None:
        parser = build_parser()
        actions = {a.dest for a in parser._actions}
        assert "proxy_host" in actions
        assert "proxy_port" in actions

    def test_parser_has_tor_group(self) -> None:
        parser = build_parser()
        actions = {a.dest for a in parser._actions}
        assert "tor_host" in actions
        assert "tor_port" in actions

    def test_parser_has_performance_options(self) -> None:
        parser = build_parser()
        actions = {a.dest for a in parser._actions}
        assert "buffer_size" in actions
        assert "backlog" in actions

    def test_parser_has_timeout_options(self) -> None:
        parser = build_parser()
        actions = {a.dest for a in parser._actions}
        assert "connect_timeout" in actions
        assert "read_timeout" in actions

    def test_parser_has_log_level(self) -> None:
        parser = build_parser()
        actions = {a.dest for a in parser._actions}
        assert "log_level" in actions

    def test_parser_has_config(self) -> None:
        parser = build_parser()
        actions = {a.dest for a in parser._actions}
        assert "config" in actions

    def test_parser_has_version(self) -> None:
        parser = build_parser()
        actions = {a.dest for a in parser._actions}
        assert "version" in actions

    def test_parse_proxy_args(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "--proxy-host",
                "0.0.0.0",
                "--proxy-port",
                "8080",
            ]
        )
        assert args.proxy_host == "0.0.0.0"
        assert args.proxy_port == 8080

    def test_parse_tor_args(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "--tor-host",
                "10.0.0.1",
                "--tor-port",
                "9150",
            ]
        )
        assert args.tor_host == "10.0.0.1"
        assert args.tor_port == 9150

    def test_parse_perf_args(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "--buffer-size",
                "16384",
                "--backlog",
                "50",
            ]
        )
        assert args.buffer_size == 16384
        assert args.backlog == 50

    def test_parse_timeout_args(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "--connect-timeout",
                "15",
                "--read-timeout",
                "120",
            ]
        )
        assert args.connect_timeout == 15
        assert args.read_timeout == 120

    def test_parse_log_level(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--log-level", "DEBUG"])
        assert args.log_level == "DEBUG"

    def test_parse_config(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--config", "config.json"])
        assert args.config == "config.json"

    def test_parse_version(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--version"])
        assert args.version is True

    def test_parse_no_args(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        assert args.proxy_host is None
        assert args.proxy_port is None
        assert args.tor_host is None
        assert args.tor_port is None
        assert args.buffer_size is None
        assert args.backlog is None
        assert args.connect_timeout is None
        assert args.read_timeout is None
        assert args.log_level is None
        assert args.config is None
        assert args.version is False


class TestApplyCliOverrides:
    """Tests for _apply_cli_overrides."""

    def test_no_overrides(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        overrides = _apply_cli_overrides(parser, args)
        assert overrides == {}

    def test_proxy_overrides(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "--proxy-host",
                "0.0.0.0",
                "--proxy-port",
                "8080",
            ]
        )
        overrides = _apply_cli_overrides(parser, args)
        assert overrides["https_proxy_host"] == "0.0.0.0"
        assert overrides["https_proxy_port"] == 8080

    def test_tor_overrides(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "--tor-host",
                "10.0.0.1",
                "--tor-port",
                "9150",
            ]
        )
        overrides = _apply_cli_overrides(parser, args)
        assert overrides["tor_socks_host"] == "10.0.0.1"
        assert overrides["tor_socks_port"] == 9150

    def test_all_overrides(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "--proxy-host",
                "0.0.0.0",
                "--proxy-port",
                "8080",
                "--tor-host",
                "10.0.0.1",
                "--tor-port",
                "9150",
                "--buffer-size",
                "16384",
                "--backlog",
                "50",
                "--connect-timeout",
                "15",
                "--read-timeout",
                "120",
                "--log-level",
                "DEBUG",
                "--config",
                "config.yaml",
            ]
        )
        overrides = _apply_cli_overrides(parser, args)
        assert overrides["https_proxy_host"] == "0.0.0.0"
        assert overrides["https_proxy_port"] == 8080
        assert overrides["tor_socks_host"] == "10.0.0.1"
        assert overrides["tor_socks_port"] == 9150
        assert overrides["buffer_size"] == 16384
        assert overrides["backlog"] == 50
        assert overrides["connect_timeout"] == 15
        assert overrides["read_timeout"] == 120
        assert overrides["log_level"] == "DEBUG"
        assert overrides["config_file"] == "config.yaml"


class TestAsyncMain:
    """Tests for async_main."""

    @pytest.mark.asyncio
    async def test_async_main_starts_proxy(self, settings) -> None:
        with patch(
            "tor_https_bridge.cli.main.TorHTTPSProxy",
        ) as mock_proxy_class:
            mock_proxy = AsyncMock()
            mock_proxy.start = AsyncMock()
            mock_proxy.stop = AsyncMock()
            mock_proxy_class.return_value = mock_proxy

            with patch(
                "tor_https_bridge.cli.main.setup_logging",
            ) as mock_setup:
                with patch(
                    "tor_https_bridge.cli.main.print_banner",
                ) as mock_banner:
                    with patch(
                        "tor_https_bridge.cli.main.setup_signal_handlers",
                    ):
                        await async_main(settings)

                        mock_setup.assert_called_once_with(
                            level=settings.log_level,
                        )
                        mock_banner.assert_called_once()
                        mock_proxy_class.assert_called_once_with(settings)
                        mock_proxy.start.assert_awaited_once()
                        mock_proxy.stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_async_main_cancelled_error(self, settings) -> None:
        with patch(
            "tor_https_bridge.cli.main.TorHTTPSProxy",
        ) as mock_proxy_class:
            mock_proxy = AsyncMock()
            mock_proxy.start = AsyncMock(
                side_effect=asyncio.CancelledError(),
            )
            mock_proxy.stop = AsyncMock()
            mock_proxy_class.return_value = mock_proxy

            with patch(
                "tor_https_bridge.cli.main.setup_logging",
            ):
                with patch(
                    "tor_https_bridge.cli.main.print_banner",
                ):
                    with patch(
                        "tor_https_bridge.cli.main.setup_signal_handlers",
                    ):
                        await async_main(settings)

                        mock_proxy.start.assert_awaited_once()
                        mock_proxy.stop.assert_awaited_once()


class TestMain:
    """Tests for main CLI entry point."""

    def test_main_version(self) -> None:
        with patch(
            "sys.argv",
            ["tor-https-bridge", "--version"],
        ):
            with patch(
                "tor_https_bridge.cli.main.print",
            ) as mock_print:
                with pytest.raises(SystemExit) as exc:
                    main()

                assert exc.value.code == 0
                mock_print.assert_called_once_with(
                    "tor-https-bridge v1.0.0",
                )

    def test_main_keyboard_interrupt(self) -> None:
        with patch(
            "sys.argv",
            ["tor-https-bridge"],
        ):
            with patch(
                "tor_https_bridge.cli.main.asyncio.run",
                side_effect=KeyboardInterrupt(),
            ):
                with patch(
                    "builtins.print",
                ) as mock_print:
                    with patch(
                        "sys.exit",
                    ) as mock_exit:
                        main()
                        mock_exit.assert_called_once_with(0)
                        # print is called with '\n' prefix from the source
                        mock_print.assert_called_once()

    def test_main_with_cli_overrides(self) -> None:
        with patch(
            "sys.argv",
            [
                "tor-https-bridge",
                "--proxy-port",
                "8080",
                "--log-level",
                "DEBUG",
            ],
        ):
            with patch(
                "tor_https_bridge.cli.main.asyncio.run",
            ) as mock_run:
                main()
                mock_run.assert_called_once()

    def test_main_default(self) -> None:
        with patch(
            "sys.argv",
            ["tor-https-bridge"],
        ):
            with patch(
                "tor_https_bridge.cli.main.asyncio.run",
            ) as mock_run:
                main()
                mock_run.assert_called_once()
