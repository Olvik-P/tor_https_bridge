"""REST API for Tor HTTPS Bridge Proxy web interface."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiohttp import web

from tor_https_bridge.config.constants import (
    BACKLOG_SIZE,
    BUFFER_SIZE,
    CONNECT_TIMEOUT,
    DEFAULT_ACCEPT_LANGUAGE,
    DEFAULT_USER_AGENT,
    HTTPS_PROXY_DEFAULT_HOST,
    HTTPS_PROXY_DEFAULT_PORT,
    MAX_REQUEST_SIZE,
    READ_TIMEOUT,
    SANITIZE_HEADERS_DEFAULT,
    SOCKS_PROXY_DEFAULT_HOST,
    SOCKS_PROXY_DEFAULT_PORT,
    SOCKS_RETRY_COUNT,
    SOCKS_RETRY_DELAY,
    TOR_SOCKS_DEFAULT_HOST,
    TOR_SOCKS_DEFAULT_PORT,
    VERSION,
)
from tor_https_bridge.config.settings import Settings
from tor_https_bridge.core.server import TorHTTPSProxy

logger = logging.getLogger(__name__)


class ProxyManager:
    """Manages the TorHTTPSProxy lifecycle via web API."""

    def __init__(self) -> None:
        self._proxy: TorHTTPSProxy | None = None
        self._settings: Settings = Settings()
        self._task: asyncio.Task | None = None
        self._running: bool = False
        self._logs: list[str] = []
        self._max_logs = 500
        self._shutdown_event: asyncio.Event | None = None

    @property
    def is_running(self) -> bool:
        return self._running and self._proxy is not None

    @property
    def settings(self) -> Settings:
        return self._settings

    def get_status(self) -> dict[str, Any]:
        return {
            "running": self.is_running,
            "version": VERSION,
            "settings": self._settings.model_dump(),
            "active_connections": len(self._proxy._active_connections)
            if self._proxy
            else 0,
        }

    def get_logs(self, limit: int = 100) -> list[str]:
        return self._logs[-limit:]

    def add_log(self, message: str) -> None:
        self._logs.append(message)
        if len(self._logs) > self._max_logs:
            self._logs = self._logs[-self._max_logs :]

    async def start(
        self, settings_dict: dict[str, Any] | None = None
    ) -> dict[str, str]:
        if self.is_running:
            return {"error": "Proxy is already running"}

        try:
            if settings_dict:
                merged = {**self._settings.model_dump(), **settings_dict}
                self._settings = Settings(**merged)

            self._proxy = TorHTTPSProxy(self._settings)
            self._running = True

            async def _run_proxy() -> None:
                try:
                    await self._proxy.start()
                except asyncio.CancelledError:
                    pass
                except Exception as exc:
                    self.add_log(f"[ERROR] Proxy crashed: {exc}")
                finally:
                    self._running = False

            self._task = asyncio.create_task(_run_proxy())
            self.add_log("[SYSTEM] Proxy started")
            return {"status": "started"}
        except Exception as e:
            self._running = False
            self.add_log(f"[ERROR] Failed to start: {e}")
            return {"error": str(e)}

    async def stop(self) -> dict[str, str]:
        if not self.is_running or self._proxy is None:
            return {"error": "Proxy is not running"}

        try:
            self._running = False
            await self._proxy.stop()

            if self._task and not self._task.done():
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass

            self._proxy = None
            self._task = None
            self.add_log("[SYSTEM] Proxy stopped")
            return {"status": "stopped"}
        except Exception as e:
            self.add_log(f"[ERROR] Failed to stop: {e}")
            return {"error": str(e)}

    async def shutdown(self) -> None:
        """Stop proxy and signal the web server to shut down."""
        self.add_log("[SYSTEM] Shutdown requested")
        if self.is_running:
            await self.stop()
        if self._shutdown_event:
            self._shutdown_event.set()

    def update_settings(self, settings_dict: dict[str, Any]) -> dict[str, str]:
        try:
            merged = {**self._settings.model_dump(), **settings_dict}
            self._settings = Settings(**merged)
            self.add_log(f"[SYSTEM] Settings updated: {settings_dict}")
            return {"status": "updated", "settings": self._settings.model_dump()}
        except Exception as e:
            return {"error": str(e)}

    def get_defaults(self) -> dict[str, Any]:
        return {
            "tor_socks_host": TOR_SOCKS_DEFAULT_HOST,
            "tor_socks_port": TOR_SOCKS_DEFAULT_PORT,
            "https_proxy_host": HTTPS_PROXY_DEFAULT_HOST,
            "https_proxy_port": HTTPS_PROXY_DEFAULT_PORT,
            "socks_proxy_host": SOCKS_PROXY_DEFAULT_HOST,
            "socks_proxy_port": SOCKS_PROXY_DEFAULT_PORT,
            "buffer_size": BUFFER_SIZE,
            "backlog": BACKLOG_SIZE,
            "max_request_size": MAX_REQUEST_SIZE,
            "connect_timeout": CONNECT_TIMEOUT,
            "read_timeout": READ_TIMEOUT,
            "socks_retry_count": SOCKS_RETRY_COUNT,
            "socks_retry_delay": SOCKS_RETRY_DELAY,
            "sanitize_headers": SANITIZE_HEADERS_DEFAULT,
            "override_user_agent": DEFAULT_USER_AGENT,
            "override_accept_language": DEFAULT_ACCEPT_LANGUAGE,
        }


manager = ProxyManager()


async def handle_status(request: web.Request) -> web.Response:
    return web.json_response(manager.get_status())


async def handle_start(request: web.Request) -> web.Response:
    data = await request.json() if request.content_type == "application/json" else {}
    result = await manager.start(data if data else None)
    status = 400 if "error" in result else 200
    return web.json_response(result, status=status)


async def handle_stop(request: web.Request) -> web.Response:
    result = await manager.stop()
    status = 400 if "error" in result else 200
    return web.json_response(result, status=status)


async def handle_shutdown(request: web.Request) -> web.Response:
    asyncio.create_task(manager.shutdown())
    return web.json_response({"status": "shutting_down"})


async def handle_settings(request: web.Request) -> web.Response:
    if request.method == "GET":
        return web.json_response(manager.settings.model_dump())

    data = await request.json()
    result = manager.update_settings(data)
    status = 400 if "error" in result else 200
    return web.json_response(result, status=status)


async def handle_defaults(request: web.Request) -> web.Response:
    return web.json_response(manager.get_defaults())


async def handle_logs(request: web.Request) -> web.Response:
    limit = int(request.query.get("limit", "100"))
    return web.json_response(manager.get_logs(limit))


async def websocket_handler(request: web.Request) -> web.WebSocketResponse:
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    last_sent = 0
    try:
        while not ws.closed:
            logs = manager.get_logs()
            if len(logs) > last_sent:
                new_logs = logs[last_sent:]
                last_sent = len(logs)
                for log in new_logs:
                    await ws.send_str(log)
            await asyncio.sleep(0.5)
    except Exception:
        pass

    return ws


def create_api_app() -> web.Application:
    app = web.Application()

    app.router.add_get("/api/status", handle_status)
    app.router.add_post("/api/start", handle_start)
    app.router.add_post("/api/stop", handle_stop)
    app.router.add_post("/api/shutdown", handle_shutdown)
    app.router.add_get("/api/settings", handle_settings)
    app.router.add_put("/api/settings", handle_settings)
    app.router.add_get("/api/defaults", handle_defaults)
    app.router.add_get("/api/logs", handle_logs)
    app.router.add_get("/ws/logs", websocket_handler)

    return app
