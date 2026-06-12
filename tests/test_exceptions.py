"""Tests for tor_https_bridge.core.exceptions."""

from __future__ import annotations

from tor_https_bridge.core.exceptions import (
    ConfigurationError,
    ProxyConnectionError,
    ProxyProtocolError,
    ProxyShutdownError,
    ProxyTimeoutError,
    TorBridgeError,
)


class TestTorBridgeError:
    """Tests for base TorBridgeError."""

    def test_base_exception(self) -> None:
        err = TorBridgeError("base error")
        assert isinstance(err, Exception)
        assert str(err) == "base error"

    def test_base_exception_is_base(self) -> None:
        """All custom exceptions should inherit from TorBridgeError."""
        assert issubclass(ProxyProtocolError, TorBridgeError)
        assert issubclass(ProxyConnectionError, TorBridgeError)
        assert issubclass(ProxyTimeoutError, TorBridgeError)
        assert issubclass(ProxyShutdownError, TorBridgeError)
        assert issubclass(ConfigurationError, TorBridgeError)


class TestProxyProtocolError:
    """Tests for ProxyProtocolError."""

    def test_default_message(self) -> None:
        err = ProxyProtocolError()
        assert isinstance(err, TorBridgeError)
        assert isinstance(err, Exception)

    def test_custom_message(self) -> None:
        err = ProxyProtocolError("Malformed CONNECT request")
        assert str(err) == "Malformed CONNECT request"

    def test_chaining(self) -> None:
        cause = ValueError("invalid port")
        err = ProxyProtocolError("Parse error")
        err.__cause__ = cause
        assert err.__cause__ is cause


class TestProxyConnectionError:
    """Tests for ProxyConnectionError."""

    def test_default_message(self) -> None:
        err = ProxyConnectionError()
        assert isinstance(err, TorBridgeError)

    def test_custom_message(self) -> None:
        err = ProxyConnectionError("Failed to connect to upstream")
        assert str(err) == "Failed to connect to upstream"


class TestProxyTimeoutError:
    """Tests for ProxyTimeoutError."""

    def test_default_message(self) -> None:
        err = ProxyTimeoutError()
        assert isinstance(err, TorBridgeError)

    def test_custom_message(self) -> None:
        err = ProxyTimeoutError("Connection timed out after 30s")
        assert str(err) == "Connection timed out after 30s"


class TestProxyShutdownError:
    """Tests for ProxyShutdownError."""

    def test_default_message(self) -> None:
        err = ProxyShutdownError()
        assert isinstance(err, TorBridgeError)

    def test_custom_message(self) -> None:
        err = ProxyShutdownError("Error during shutdown")
        assert str(err) == "Error during shutdown"


class TestConfigurationError:
    """Tests for ConfigurationError."""

    def test_default_message(self) -> None:
        err = ConfigurationError()
        assert isinstance(err, TorBridgeError)

    def test_custom_message(self) -> None:
        err = ConfigurationError("Missing required config")
        assert str(err) == "Missing required config"


class TestExceptionHierarchy:
    """Tests for the complete exception hierarchy."""

    def test_catch_base_exception(self) -> None:
        """All custom exceptions should be catchable as TorBridgeError."""
        exceptions = [
            ProxyProtocolError("test"),
            ProxyConnectionError("test"),
            ProxyTimeoutError("test"),
            ProxyShutdownError("test"),
            ConfigurationError("test"),
        ]

        for exc in exceptions:
            assert isinstance(exc, TorBridgeError)
            assert isinstance(exc, Exception)

    def test_exception_string_representation(self) -> None:
        err = ProxyProtocolError("protocol violation")
        assert repr(err) == "ProxyProtocolError('protocol violation')"
