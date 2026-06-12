"""Tests for tor_https_bridge package init and __main__."""

from __future__ import annotations

import tor_https_bridge
from tor_https_bridge import VERSION, TorHTTPSProxy, __version__


class TestPackageInit:
    """Tests for tor_https_bridge.__init__."""

    def test_version_exported(self) -> None:
        assert VERSION == "1.0.0"

    def test_version_attribute(self) -> None:
        assert __version__ == "1.0.0"

    def test_tor_https_proxy_exported(self) -> None:
        assert TorHTTPSProxy is not None

    def test_all_exports(self) -> None:
        expected = {"TorHTTPSProxy", "VERSION"}
        assert set(tor_https_bridge.__all__) == expected

    def test_docstring_present(self) -> None:
        assert tor_https_bridge.__doc__ is not None
        assert "Tor HTTPS Bridge Proxy" in tor_https_bridge.__doc__


class TestPackageMain:
    """Tests for tor_https_bridge.__main__."""

    def test_main_module_exists(self) -> None:
        """__main__ module should exist and be importable."""
        import importlib
        import importlib.util

        spec = importlib.util.find_spec("tor_https_bridge.__main__")
        assert spec is not None
        assert spec.origin is not None


class TestPackageVersion:
    """Tests for package version consistency."""

    def test_version_consistency(self) -> None:
        """VERSION constant and __version__ should match."""
        assert VERSION == __version__

    def test_version_string_format(self) -> None:
        """Version should follow semver format."""
        parts = VERSION.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)
