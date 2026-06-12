"""HTTP header sanitizer for anonymizing outgoing requests in stealth mode.

The sanitizer removes or replaces HTTP headers that can leak identifying
information such as locale, operating system, and internal IP addresses.

Usage::

    from tor_https_bridge.core.sanitizer import HeaderSanitizer

    sanitizer = HeaderSanitizer()
    raw = b'GET / HTTP/1.1\\r\\nAccept-Language: ru-RU\\r\\n\\r\\n'
    clean = sanitizer.sanitize(raw)
"""

from __future__ import annotations

import logging
from typing import Final

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sensitive headers that reveal internal IP, network topology, or client
# identity.  These are **removed** entirely from outgoing requests.
# ---------------------------------------------------------------------------
SENSITIVE_HEADERS: Final[frozenset[str]] = frozenset(
    {
        "x-forwarded-for",
        "x-real-ip",
        "client-ip",
        "x-client-ip",
        "x-forwarded",
        "forwarded",
        "via",
        "x-request-id",
        "x-trace-id",
        "x-user-id",
        "x-country-code",
        "x-geo-location",
        "x-client-locale",
        "x-device-user-agent",
        "x-originating-ip",
        "x-remote-ip",
        "x-remote-addr",
        "x-arr-log-id",
        "x-akamai-trans-id",
    }
)

# ---------------------------------------------------------------------------
# Default neutral values for header replacement.
# ---------------------------------------------------------------------------

DEFAULT_USER_AGENT: Final[str] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)
"""Default neutral User-Agent (English, Windows, Chrome 125)."""

DEFAULT_ACCEPT_LANGUAGE: Final[str] = "en-US,en;q=0.9"
"""Default neutral Accept-Language (English US)."""


class HeaderSanitizer:
    """Sanitizes HTTP headers to remove identifying information.

    Performs three operations on HTTP request headers:

    1. **Removes** headers that leak internal IP / network topology
       (e.g. ``X-Forwarded-For``, ``X-Real-IP``, ``Via``).
    2. **Replaces** ``User-Agent`` with a neutral English-language value.
    3. **Replaces** ``Accept-Language`` with ``en-US,en;q=0.9``.

    Headers that are not in the sensitive list and are not
    ``User-Agent`` or ``Accept-Language`` are passed through unchanged.

    If ``User-Agent`` or ``Accept-Language`` are missing from the original
    request, they are **added** with the neutral values.

    Args:
        override_user_agent:
            Custom User-Agent string.  Defaults to :data:`DEFAULT_USER_AGENT`.
        override_accept_language:
            Custom Accept-Language string.
            Defaults to :data:`DEFAULT_ACCEPT_LANGUAGE`.
    """

    def __init__(
        self,
        override_user_agent: str = DEFAULT_USER_AGENT,
        override_accept_language: str = DEFAULT_ACCEPT_LANGUAGE,
    ) -> None:
        self._user_agent = override_user_agent
        self._accept_language = override_accept_language

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def sanitize(self, request_data: bytes) -> bytes:
        """Sanitize headers in an HTTP request.

        Splits the request at the ``\\r\\n\\r\\n`` boundary, processes
        each header line, and reassembles the request.  The request body
        (if any) is preserved verbatim.

        Args:
            request_data: Raw HTTP request bytes.

        Returns:
            Sanitized HTTP request bytes with identifying headers
            removed or replaced.
        """
        header_part, sep, body = request_data.partition(b"\r\n\r\n")

        if not sep:
            # No body — the entire request is headers
            header_part = request_data
            body = b""

        lines = header_part.split(b"\r\n")
        if not lines:
            return request_data

        request_line = lines[0]
        sanitized_headers: list[bytes] = [request_line]

        header_names_seen: set[str] = set()

        for line in lines[1:]:
            if not line or b":" not in line:
                # Preserve empty lines (shouldn't happen before body,
                # but be safe)
                sanitized_headers.append(line)
                continue

            name_raw, _sep, value = line.partition(b":")
            name = name_raw.decode("ascii", errors="replace").strip().lower()

            if name in SENSITIVE_HEADERS:
                logger.debug("Removed sensitive header: %s", name)
                continue

            if name == "user-agent":
                sanitized_headers.append(
                    f"User-Agent: {self._user_agent}".encode(),
                )
                header_names_seen.add("user-agent")
                logger.debug(
                    "Replaced User-Agent: %s -> %s",
                    value.decode("ascii", errors="replace").strip(),
                    self._user_agent,
                )
                continue

            if name == "accept-language":
                sanitized_headers.append(
                    f"Accept-Language: {self._accept_language}".encode(),
                )
                header_names_seen.add("accept-language")
                logger.debug(
                    "Replaced Accept-Language: %s -> %s",
                    value.decode("ascii", errors="replace").strip(),
                    self._accept_language,
                )
                continue

            # Pass through all other headers unchanged
            sanitized_headers.append(line)

        # Add mandatory headers if they were missing
        if "user-agent" not in header_names_seen:
            sanitized_headers.append(
                f"User-Agent: {self._user_agent}".encode(),
            )
        if "accept-language" not in header_names_seen:
            sanitized_headers.append(
                f"Accept-Language: {self._accept_language}".encode(),
            )

        # Reassemble
        result = b"\r\n".join(sanitized_headers)
        if body:
            result += b"\r\n\r\n" + body

        return result
