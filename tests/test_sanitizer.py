"""Tests for tor_https_bridge.core.sanitizer."""

from __future__ import annotations

from tor_https_bridge.core.sanitizer import (
    DEFAULT_ACCEPT_LANGUAGE,
    DEFAULT_USER_AGENT,
    HeaderSanitizer,
)


class TestHeaderSanitizerDefaults:
    """Tests for HeaderSanitizer with default values."""

    def test_sanitize_removes_x_forwarded_for(self) -> None:
        sanitizer = HeaderSanitizer()
        raw = (
            b"GET / HTTP/1.1\r\n"
            b"Host: example.com\r\n"
            b"X-Forwarded-For: 10.0.0.1\r\n"
            b"\r\n"
        )
        result = sanitizer.sanitize(raw)
        assert b"X-Forwarded-For" not in result
        assert b"x-forwarded-for" not in result

    def test_sanitize_removes_x_real_ip(self) -> None:
        sanitizer = HeaderSanitizer()
        raw = (
            b"GET / HTTP/1.1\r\n"
            b"Host: example.com\r\n"
            b"X-Real-IP: 192.168.1.1\r\n"
            b"\r\n"
        )
        result = sanitizer.sanitize(raw)
        assert b"X-Real-IP" not in result

    def test_sanitize_removes_via_header(self) -> None:
        sanitizer = HeaderSanitizer()
        raw = (
            b"GET / HTTP/1.1\r\n"
            b"Host: example.com\r\n"
            b"Via: 1.1 proxy.local\r\n"
            b"\r\n"
        )
        result = sanitizer.sanitize(raw)
        assert b"Via" not in result

    def test_sanitize_removes_forwarded(self) -> None:
        sanitizer = HeaderSanitizer()
        raw = (
            b"GET / HTTP/1.1\r\n"
            b"Host: example.com\r\n"
            b"Forwarded: for=10.0.0.1;proto=http\r\n"
            b"\r\n"
        )
        result = sanitizer.sanitize(raw)
        assert b"Forwarded" not in result

    def test_sanitize_replaces_user_agent(self) -> None:
        sanitizer = HeaderSanitizer()
        raw = (
            b"GET / HTTP/1.1\r\n"
            b"Host: example.com\r\n"
            b"User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64; ru)\r\n"
            b"\r\n"
        )
        result = sanitizer.sanitize(raw)
        assert DEFAULT_USER_AGENT.encode() in result
        assert b"ru)" not in result

    def test_sanitize_replaces_accept_language(self) -> None:
        sanitizer = HeaderSanitizer()
        raw = (
            b"GET / HTTP/1.1\r\n"
            b"Host: example.com\r\n"
            b"Accept-Language: ru-RU,ru;q=0.9\r\n"
            b"\r\n"
        )
        result = sanitizer.sanitize(raw)
        assert DEFAULT_ACCEPT_LANGUAGE.encode() in result
        assert b"ru-RU" not in result

    def test_sanitize_preserves_other_headers(self) -> None:
        sanitizer = HeaderSanitizer()
        raw = (
            b"GET / HTTP/1.1\r\n"
            b"Host: example.com\r\n"
            b"Accept: text/html\r\n"
            b"Cache-Control: no-cache\r\n"
            b"\r\n"
        )
        result = sanitizer.sanitize(raw)
        assert b"Host: example.com" in result
        assert b"Accept: text/html" in result
        assert b"Cache-Control: no-cache" in result

    def test_sanitize_preserves_body(self) -> None:
        sanitizer = HeaderSanitizer()
        raw = (
            b"POST /api HTTP/1.1\r\n"
            b"Host: example.com\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Length: 16\r\n"
            b"\r\n"
            b'{"key": "value"}'
        )
        result = sanitizer.sanitize(raw)
        assert result.endswith(b'{"key": "value"}')
        assert b"Content-Type: application/json" in result

    def test_sanitize_adds_missing_user_agent(self) -> None:
        sanitizer = HeaderSanitizer()
        raw = b"GET / HTTP/1.1\r\n" b"Host: example.com\r\n" b"\r\n"
        result = sanitizer.sanitize(raw)
        assert DEFAULT_USER_AGENT.encode() in result

    def test_sanitize_adds_missing_accept_language(self) -> None:
        sanitizer = HeaderSanitizer()
        raw = b"GET / HTTP/1.1\r\n" b"Host: example.com\r\n" b"\r\n"
        result = sanitizer.sanitize(raw)
        assert DEFAULT_ACCEPT_LANGUAGE.encode() in result

    def test_sanitize_empty_request(self) -> None:
        sanitizer = HeaderSanitizer()
        result = sanitizer.sanitize(b"")
        # Empty input should return empty (or just added headers)
        assert isinstance(result, bytes)

    def test_sanitize_request_line_only(self) -> None:
        sanitizer = HeaderSanitizer()
        raw = b"GET / HTTP/1.1\r\n"
        result = sanitizer.sanitize(raw)
        # Should have request line + added headers
        assert result.startswith(b"GET / HTTP/1.1")
        assert DEFAULT_USER_AGENT.encode() in result
        assert DEFAULT_ACCEPT_LANGUAGE.encode() in result

    def test_sanitize_removes_multiple_sensitive_headers(self) -> None:
        sanitizer = HeaderSanitizer()
        raw = (
            b"GET / HTTP/1.1\r\n"
            b"Host: example.com\r\n"
            b"X-Forwarded-For: 10.0.0.1\r\n"
            b"X-Real-IP: 192.168.1.1\r\n"
            b"Client-IP: 10.0.0.1\r\n"
            b"X-Request-ID: abc-123\r\n"
            b"\r\n"
        )
        result = sanitizer.sanitize(raw)
        assert b"X-Forwarded-For" not in result
        assert b"X-Real-IP" not in result
        assert b"Client-IP" not in result
        assert b"X-Request-ID" not in result
        assert b"Host: example.com" in result


class TestHeaderSanitizerCustom:
    """Tests for HeaderSanitizer with custom values."""

    def test_custom_user_agent(self) -> None:
        custom_ua = "CustomAgent/1.0"
        sanitizer = HeaderSanitizer(override_user_agent=custom_ua)
        raw = b"GET / HTTP/1.1\r\n" b"Host: example.com\r\n" b"\r\n"
        result = sanitizer.sanitize(raw)
        assert custom_ua.encode() in result

    def test_custom_accept_language(self) -> None:
        custom_al = "de-DE,de;q=0.9"
        sanitizer = HeaderSanitizer(override_accept_language=custom_al)
        raw = b"GET / HTTP/1.1\r\n" b"Host: example.com\r\n" b"\r\n"
        result = sanitizer.sanitize(raw)
        assert custom_al.encode() in result

    def test_custom_both_values(self) -> None:
        custom_ua = "TestAgent/2.0"
        custom_al = "fr-FR,fr;q=0.9"
        sanitizer = HeaderSanitizer(
            override_user_agent=custom_ua,
            override_accept_language=custom_al,
        )
        raw = (
            b"GET / HTTP/1.1\r\n"
            b"Host: example.com\r\n"
            b"User-Agent: OldAgent/1.0\r\n"
            b"Accept-Language: ru-RU\r\n"
            b"\r\n"
        )
        result = sanitizer.sanitize(raw)
        assert custom_ua.encode() in result
        assert custom_al.encode() in result
        assert b"OldAgent" not in result
        assert b"ru-RU" not in result


class TestHeaderSanitizerEdgeCases:
    """Tests for edge cases in HeaderSanitizer."""

    def test_sanitize_no_body_no_trailing_crlf(self) -> None:
        """Request without body and without trailing CRLF."""
        sanitizer = HeaderSanitizer()
        raw = b"GET / HTTP/1.1\r\nHost: example.com\r\nUser-Agent: test\r\n"
        result = sanitizer.sanitize(raw)
        assert DEFAULT_USER_AGENT.encode() in result
        assert b"test" not in result

    def test_sanitize_headers_case_insensitive(self) -> None:
        """Sensitive headers should be detected case-insensitively."""
        sanitizer = HeaderSanitizer()
        raw = (
            b"GET / HTTP/1.1\r\n"
            b"Host: example.com\r\n"
            b"x-forwarded-for: 10.0.0.1\r\n"
            b"X-REAL-IP: 192.168.1.1\r\n"
            b"\r\n"
        )
        result = sanitizer.sanitize(raw)
        assert b"x-forwarded-for" not in result
        assert b"X-REAL-IP" not in result

    def test_sanitize_preserves_cookies(self) -> None:
        """Cookies should be preserved (they are encrypted in HTTPS)."""
        sanitizer = HeaderSanitizer()
        raw = (
            b"GET / HTTP/1.1\r\n"
            b"Host: example.com\r\n"
            b"Cookie: session=abc123\r\n"
            b"\r\n"
        )
        result = sanitizer.sanitize(raw)
        assert b"Cookie: session=abc123" in result

    def test_sanitize_preserves_authorization(self) -> None:
        """Authorization headers should be preserved."""
        sanitizer = HeaderSanitizer()
        raw = (
            b"GET / HTTP/1.1\r\n"
            b"Host: example.com\r\n"
            b"Authorization: Bearer token123\r\n"
            b"\r\n"
        )
        result = sanitizer.sanitize(raw)
        assert b"Authorization: Bearer token123" in result
