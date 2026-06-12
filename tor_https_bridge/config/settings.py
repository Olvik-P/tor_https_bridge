"""Configuration settings for Tor HTTPS Bridge Proxy.

Uses Pydantic v2 for settings validation with support for:
- Environment variables (prefix ``TOR_BRIDGE_``)
- ``.env`` file
- Direct instantiation
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from tor_https_bridge.config.constants import (
    BACKLOG_SIZE,
    BUFFER_SIZE,
    CONNECT_TIMEOUT,
    DEFAULT_ACCEPT_LANGUAGE,
    DEFAULT_USER_AGENT,
    ENV_PREFIX,
    HTTPS_PROXY_DEFAULT_HOST,
    HTTPS_PROXY_DEFAULT_PORT,
    MAX_PORT,
    MAX_REQUEST_SIZE,
    MIN_PORT,
    READ_TIMEOUT,
    SANITIZE_HEADERS_DEFAULT,
    SOCKS_RETRY_COUNT,
    SOCKS_RETRY_DELAY,
    TOR_SOCKS_DEFAULT_HOST,
    TOR_SOCKS_DEFAULT_PORT,
)

_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


class Settings(BaseSettings):
    """Application settings with validation.

    Loads configuration from environment variables (prefix ``TOR_BRIDGE_``),
    ``.env`` file, or defaults defined in
    :mod:`tor_https_bridge.config.constants`.

    Usage::

        from tor_https_bridge.config.settings import Settings

        settings = Settings()
        settings = Settings(tor_socks_host='10.0.0.1',
                            https_proxy_port=8080)

    Environment variable examples::

        TOR_BRIDGE_TOR_SOCKS_HOST=10.0.0.1
        TOR_BRIDGE_TOR_SOCKS_PORT=9050
        TOR_BRIDGE_HTTPS_PROXY_PORT=3128
        TOR_BRIDGE_LOG_LEVEL=DEBUG
    """

    model_config = SettingsConfigDict(
        env_prefix=ENV_PREFIX,
        env_file=".env",
        env_file_encoding="utf-8",
        frozen=True,
        extra="ignore",
    )

    # --- Tor SOCKS5 ---
    tor_socks_host: str = Field(
        default=TOR_SOCKS_DEFAULT_HOST,
        description="Tor SOCKS5 host address",
    )
    tor_socks_port: int = Field(
        default=TOR_SOCKS_DEFAULT_PORT,
        description="Tor SOCKS5 port",
        ge=MIN_PORT,
        le=MAX_PORT,
    )

    # --- HTTPS Proxy ---
    https_proxy_host: str = Field(
        default=HTTPS_PROXY_DEFAULT_HOST,
        description="HTTPS proxy listen host",
    )
    https_proxy_port: int = Field(
        default=HTTPS_PROXY_DEFAULT_PORT,
        description="HTTPS proxy listen port",
        ge=MIN_PORT,
        le=MAX_PORT,
    )

    # --- Performance ---
    backlog: int = Field(
        default=BACKLOG_SIZE,
        description="Maximum pending connections",
        ge=1,
        le=65535,
    )
    buffer_size: int = Field(
        default=BUFFER_SIZE,
        description="Buffer size for data forwarding (bytes)",
        ge=1024,
        le=1048576,
    )
    max_request_size: int = Field(
        default=MAX_REQUEST_SIZE,
        description="Maximum HTTP CONNECT request size (bytes)",
        ge=1024,
        le=1048576,
    )

    # --- Timeouts ---
    connect_timeout: int = Field(
        default=CONNECT_TIMEOUT,
        description="Upstream connection timeout (seconds)",
        ge=1,
        le=300,
    )
    read_timeout: int = Field(
        default=READ_TIMEOUT,
        description="Upstream read timeout (seconds)",
        ge=1,
        le=3600,
    )

    # --- Retry ---
    socks_retry_count: int = Field(
        default=SOCKS_RETRY_COUNT,
        description="Number of SOCKS5 connection retry attempts",
        ge=0,
        le=10,
    )
    socks_retry_delay: float = Field(
        default=SOCKS_RETRY_DELAY,
        description="Delay in seconds between SOCKS5 connection retries",
        ge=0.1,
        le=30.0,
    )

    # --- Logging ---
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )

    # --- Stealth Mode (Header Sanitization) ---
    sanitize_headers: bool = Field(
        default=SANITIZE_HEADERS_DEFAULT,
        description="Enable HTTP header sanitization for stealth mode",
    )
    override_user_agent: str = Field(
        default=DEFAULT_USER_AGENT,
        description="Custom User-Agent for sanitized requests",
        min_length=10,
        max_length=512,
    )
    override_accept_language: str = Field(
        default=DEFAULT_ACCEPT_LANGUAGE,
        description="Custom Accept-Language for sanitized requests",
        min_length=2,
        max_length=100,
    )

    # --- Optional config file ---
    config_file: Optional[str] = Field(
        default=None,
        description="Path to JSON/YAML config file",
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is a valid logging level name."""
        upper = v.upper()
        if upper not in _LOG_LEVELS:
            msg = (
                f"Invalid log level: {v}. "
                f'Choose from {", ".join(sorted(_LOG_LEVELS))}'
            )
            raise ValueError(msg)
        return upper

    @field_validator("tor_socks_host", "https_proxy_host")
    @classmethod
    def validate_host(cls, v: str) -> str:
        """Validate hostname is not empty and within length limits."""
        if not v or len(v) > 255:
            msg = f"Invalid host: {v!r}"
            raise ValueError(msg)
        return v


def load_settings() -> Settings:
    """Load settings with optional JSON/YAML config file support.

    Returns:
        Settings: Fully resolved application settings.
    """
    settings = Settings()

    if settings.config_file:
        path = Path(settings.config_file)
        if not path.exists():
            import warnings

            warnings.warn(f"Config file not found: {path}", stacklevel=2)
            return settings

        suffix = path.suffix.lower()
        if suffix in (".json", ".yaml", ".yml"):
            import json

            if suffix == ".json":
                with open(path) as f:
                    data = json.load(f)
            else:
                try:
                    import yaml  # type: ignore[import-untyped]
                except ImportError:
                    raise ImportError(
                        "PyYAML is required for YAML config files. "
                        "Install with: pip install pyyaml"
                    )
                with open(path) as f:
                    data = yaml.safe_load(f)

            # Merge with env vars taking precedence
            merged = settings.model_dump()
            merged.update({k.lower(): v for k, v in data.items()})
            return Settings(**merged)

    return settings
