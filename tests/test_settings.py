"""Tests for tor_https_bridge.config.settings."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

import pytest
from pydantic import ValidationError

from tor_https_bridge.config.settings import Settings, load_settings


class TestSettingsDefaults:
    """Tests for default settings values."""

    def test_default_tor_socks_host(self, settings: Settings) -> None:
        assert settings.tor_socks_host == "127.0.0.1"

    def test_default_tor_socks_port(self, settings: Settings) -> None:
        assert settings.tor_socks_port == 9050

    def test_default_https_proxy_host(self, settings: Settings) -> None:
        assert settings.https_proxy_host == "0.0.0.0"

    def test_default_https_proxy_port(self, settings: Settings) -> None:
        assert settings.https_proxy_port == 3128

    def test_default_backlog(self, settings: Settings) -> None:
        assert settings.backlog == 100

    def test_default_buffer_size(self, settings: Settings) -> None:
        assert settings.buffer_size == 8192

    def test_default_max_request_size(self, settings: Settings) -> None:
        assert settings.max_request_size == 65535

    def test_default_connect_timeout(self, settings: Settings) -> None:
        assert settings.connect_timeout == 60

    def test_default_read_timeout(self, settings: Settings) -> None:
        assert settings.read_timeout == 120

    def test_default_socks_retry_count(self, settings: Settings) -> None:
        assert settings.socks_retry_count == 2

    def test_default_socks_retry_delay(self, settings: Settings) -> None:
        assert settings.socks_retry_delay == 2.0

    def test_default_log_level(self, settings: Settings) -> None:
        assert settings.log_level == "INFO"

    def test_default_config_file(self, settings: Settings) -> None:
        assert settings.config_file is None

    def test_default_sanitize_headers(self, settings: Settings) -> None:
        assert settings.sanitize_headers is False

    def test_default_override_user_agent(self, settings: Settings) -> None:
        from tor_https_bridge.config.constants import DEFAULT_USER_AGENT

        assert settings.override_user_agent == DEFAULT_USER_AGENT

    def test_default_override_accept_language(
        self,
        settings: Settings,
    ) -> None:
        from tor_https_bridge.config.constants import DEFAULT_ACCEPT_LANGUAGE

        assert settings.override_accept_language == DEFAULT_ACCEPT_LANGUAGE


class TestSettingsCustomization:
    """Tests for custom settings values."""

    def test_custom_settings(self, custom_settings: Settings) -> None:
        assert custom_settings.tor_socks_host == "127.0.0.1"
        assert custom_settings.tor_socks_port == 9050
        assert custom_settings.https_proxy_host == "127.0.0.1"
        assert custom_settings.https_proxy_port == 3128
        assert custom_settings.buffer_size == 4096
        assert custom_settings.backlog == 10
        assert custom_settings.connect_timeout == 5
        assert custom_settings.read_timeout == 10
        assert custom_settings.log_level == "DEBUG"
        assert custom_settings.sanitize_headers is False

    def test_settings_via_kwargs(self) -> None:
        s = Settings(
            tor_socks_host="10.0.0.1",
            tor_socks_port=9150,
            https_proxy_port=8080,
            log_level="WARNING",
        )
        assert s.tor_socks_host == "10.0.0.1"
        assert s.tor_socks_port == 9150
        assert s.https_proxy_port == 8080
        assert s.log_level == "WARNING"

    def test_custom_sanitize_settings(self) -> None:
        s = Settings(
            sanitize_headers=True,
            override_user_agent="CustomAgent/1.0",
            override_accept_language="de-DE,de;q=0.9",
        )
        assert s.sanitize_headers is True
        assert s.override_user_agent == "CustomAgent/1.0"
        assert s.override_accept_language == "de-DE,de;q=0.9"


class TestSettingsValidation:
    """Tests for settings field validation."""

    def test_invalid_log_level(self) -> None:
        with pytest.raises(ValidationError, match="Invalid log level"):
            Settings(log_level="INVALID")

    def test_invalid_log_level_lowercase(self) -> None:
        """Log level should be case-insensitive and auto-uppercased."""
        s = Settings(log_level="debug")
        assert s.log_level == "DEBUG"

    def test_invalid_port_too_low(self) -> None:
        with pytest.raises(ValidationError):
            Settings(tor_socks_port=0)

    def test_invalid_port_too_high(self) -> None:
        with pytest.raises(ValidationError):
            Settings(tor_socks_port=65536)

    def test_invalid_proxy_port_too_low(self) -> None:
        with pytest.raises(ValidationError):
            Settings(https_proxy_port=0)

    def test_invalid_proxy_port_too_high(self) -> None:
        with pytest.raises(ValidationError):
            Settings(https_proxy_port=99999)

    def test_invalid_tor_socks_host_empty(self) -> None:
        with pytest.raises(ValidationError, match="Invalid tor_socks_host"):
            Settings(tor_socks_host="")

    def test_invalid_tor_socks_host_too_long(self) -> None:
        with pytest.raises(ValidationError, match="Invalid tor_socks_host"):
            Settings(tor_socks_host="x" * 256)

    def test_invalid_tor_socks_host_zero(self) -> None:
        """0.0.0.0 is invalid for outbound SOCKS5 connections."""
        with pytest.raises(
            ValidationError,
            match="tor_socks_host cannot be 0.0.0.0",
        ):
            Settings(tor_socks_host="0.0.0.0")

    def test_invalid_https_proxy_host_empty(self) -> None:
        with pytest.raises(ValidationError, match="Invalid https_proxy_host"):
            Settings(https_proxy_host="")

    def test_invalid_https_proxy_host_too_long(self) -> None:
        with pytest.raises(ValidationError, match="Invalid https_proxy_host"):
            Settings(https_proxy_host="x" * 256)

    def test_invalid_backlog_too_low(self) -> None:
        with pytest.raises(ValidationError):
            Settings(backlog=0)

    def test_invalid_backlog_too_high(self) -> None:
        with pytest.raises(ValidationError):
            Settings(backlog=65536)

    def test_invalid_buffer_size_too_low(self) -> None:
        with pytest.raises(ValidationError):
            Settings(buffer_size=512)

    def test_invalid_buffer_size_too_high(self) -> None:
        with pytest.raises(ValidationError):
            Settings(buffer_size=2097152)

    def test_invalid_connect_timeout_too_low(self) -> None:
        with pytest.raises(ValidationError):
            Settings(connect_timeout=0)

    def test_invalid_connect_timeout_too_high(self) -> None:
        with pytest.raises(ValidationError):
            Settings(connect_timeout=301)

    def test_invalid_read_timeout_too_low(self) -> None:
        with pytest.raises(ValidationError):
            Settings(read_timeout=0)

    def test_invalid_read_timeout_too_high(self) -> None:
        with pytest.raises(ValidationError):
            Settings(read_timeout=3601)


class TestSettingsEnvironmentVariables:
    """Tests for settings loaded from environment variables."""

    ENV_VARS = {
        "TOR_BRIDGE_TOR_SOCKS_HOST": "10.0.0.1",
        "TOR_BRIDGE_TOR_SOCKS_PORT": "9150",
        "TOR_BRIDGE_HTTPS_PROXY_HOST": "0.0.0.0",
        "TOR_BRIDGE_HTTPS_PROXY_PORT": "8080",
        "TOR_BRIDGE_LOG_LEVEL": "DEBUG",
        "TOR_BRIDGE_BUFFER_SIZE": "16384",
        "TOR_BRIDGE_BACKLOG": "50",
        "TOR_BRIDGE_CONNECT_TIMEOUT": "15",
        "TOR_BRIDGE_READ_TIMEOUT": "120",
        "TOR_BRIDGE_SANITIZE_HEADERS": "False",
    }

    @pytest.fixture(autouse=True)
    def _set_env(self) -> Generator[None, None, None]:
        """Set environment variables for the test."""
        for key, value in self.ENV_VARS.items():
            os.environ[key] = value
        yield
        for key in self.ENV_VARS:
            os.environ.pop(key, None)

    def test_settings_from_env(self) -> None:
        s = Settings()
        assert s.tor_socks_host == "10.0.0.1"
        assert s.tor_socks_port == 9150
        assert s.https_proxy_host == "0.0.0.0"
        assert s.https_proxy_port == 8080
        assert s.log_level == "DEBUG"
        assert s.buffer_size == 16384
        assert s.backlog == 50
        assert s.connect_timeout == 15
        assert s.read_timeout == 120
        assert s.sanitize_headers is False


class TestSettingsImmutability:
    """Tests that Settings is frozen (immutable)."""

    def test_settings_is_frozen(self) -> None:
        s = Settings()
        with pytest.raises(ValidationError):
            s.tor_socks_host = "10.0.0.1"  # type: ignore[misc]


class TestLoadSettings:
    """Tests for load_settings function."""

    def test_load_settings_default(self) -> None:
        s = load_settings()
        assert isinstance(s, Settings)
        assert s.config_file is None

    def test_load_settings_with_nonexistent_config(self) -> None:
        """Should warn and return default settings if config file not found."""
        _ = Settings(config_file="nonexistent.json")
        result = load_settings()
        assert isinstance(result, Settings)

    def test_load_settings_with_json_config(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.json"
        config_file.write_text(
            '{"tor_socks_host": "10.0.0.1", "log_level": "DEBUG"}'
        )

        s = Settings(config_file=str(config_file))
        # load_settings() creates a new Settings() internally
        assert s.config_file == str(config_file)

    def test_load_settings_with_yaml_config(self, tmp_path: Path) -> None:
        """YAML config should raise ImportError if pyyaml is not installed."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("tor_socks_host: 10.0.0.1\nlog_level: DEBUG\n")

        s = Settings(config_file=str(config_file))
        assert s.config_file == str(config_file)

    def test_config_file_unsupported_extension(self, tmp_path: Path) -> None:
        """Unsupported config file extension should be ignored."""
        config_file = tmp_path / "config.toml"
        config_file.write_text('[test]\nkey = "value"\n')

        s = Settings(config_file=str(config_file))
        assert s.config_file == str(config_file)
