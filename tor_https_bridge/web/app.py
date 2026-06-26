"""Main web application for Tor HTTPS Bridge Proxy dashboard."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from aiohttp import web

from tor_https_bridge.web.api import create_api_app, manager

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


async def index_handler(request: web.Request) -> web.Response:
    return web.FileResponse(STATIC_DIR / "index.html")


def create_web_app() -> web.Application:
    app = create_api_app()

    app.router.add_get("/", index_handler)
    app.router.add_static("/static/", STATIC_DIR, name="static")

    return app


async def start_web_server(host: str = "0.0.0.0", port: int = 8080) -> None:
    app = create_web_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    logger.info("Web UI started on http://%s:%d", host, port)

    shutdown_event = asyncio.Event()
    manager._shutdown_event = shutdown_event

    await shutdown_event.wait()

    logger.info("Shutting down web server...")
    if manager.is_running:
        await manager.stop()
    await runner.cleanup()
