import os
import secrets
import asyncio
from contextlib import asynccontextmanager
from collections import deque
from typing import Any
from urllib.parse import urlparse

import uvicorn
from aiogram.methods.base import TelegramMethod
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from src.bot.app import create_bot, create_dispatcher


WEBHOOK_PATH = os.getenv("TELEGRAM_WEBHOOK_PATH", "/webhook")
WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL")
WEBHOOK_SECRET_TOKEN = os.getenv("TELEGRAM_WEBHOOK_SECRET_TOKEN")
WEBHOOK_HOST = os.getenv("TELEGRAM_WEBHOOK_HOST", "0.0.0.0")
WEBHOOK_PORT = int(os.getenv("TELEGRAM_WEBHOOK_PORT", "8000"))
MANAGE_TELEGRAM_WEBHOOK = os.getenv("MANAGE_TELEGRAM_WEBHOOK", "").strip().lower() in {"1", "true", "yes", "on"}


def _build_webhook_url(base_url: str, path: str) -> str:
    """
    Build the full webhook URL.

    If ``base_url`` already contains a non-root path (e.g. ``https://app.com/tgbot``),
    that path is used as-is and ``path`` is ignored — this lets operators set the
    complete webhook URL in ``TELEGRAM_WEBHOOK_URL`` without needing a separate
    ``TELEGRAM_WEBHOOK_PATH``.  When ``base_url`` has no meaningful path (bare
    domain or trailing slash only), ``path`` is appended.
    """
    parsed_url = urlparse(base_url)
    if parsed_url.path and parsed_url.path != "/":
        return base_url.rstrip("/")

    return base_url.rstrip("/") + path


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        bot = create_bot()
        dispatcher = create_dispatcher()

        if not WEBHOOK_URL:
            raise RuntimeError("TELEGRAM_WEBHOOK_URL is not set")

        workflow_data = {
            "app": app,
            "dispatcher": dispatcher,
            **dispatcher.workflow_data,
        }

        app.state.bot = bot
        app.state.dispatcher = dispatcher
        app.state.processed_update_ids = set()
        app.state.processed_update_order = deque()
        app.state.processed_update_lock = asyncio.Lock()

        await dispatcher.emit_startup(**workflow_data)

        should_manage_webhook = MANAGE_TELEGRAM_WEBHOOK and not os.getenv("VERCEL")

        if should_manage_webhook:
            await bot.set_webhook(
                url=_build_webhook_url(WEBHOOK_URL, WEBHOOK_PATH),
                drop_pending_updates=True,
                secret_token=WEBHOOK_SECRET_TOKEN or None,
            )

        yield

        if should_manage_webhook:
            await bot.delete_webhook(drop_pending_updates=True)
        await dispatcher.emit_shutdown(**workflow_data)
        await bot.session.close()

    app = FastAPI(lifespan=lifespan)

    @app.post(WEBHOOK_PATH)
    async def telegram_webhook(request: Request) -> JSONResponse:
        bot = request.app.state.bot
        dispatcher = request.app.state.dispatcher
        payload: dict[str, Any] = await request.json()

        update_id = payload.get("update_id")
        if isinstance(update_id, int):
            async with request.app.state.processed_update_lock:
                processed_update_ids: set[int] = request.app.state.processed_update_ids
                processed_update_order: deque[int] = request.app.state.processed_update_order

                if update_id in processed_update_ids:
                    return JSONResponse(content={})

                processed_update_ids.add(update_id)
                processed_update_order.append(update_id)

                while len(processed_update_order) > 1000:
                    oldest_update_id = processed_update_order.popleft()
                    processed_update_ids.discard(oldest_update_id)

        if WEBHOOK_SECRET_TOKEN:
            secret_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
            if not secrets.compare_digest(secret_token, WEBHOOK_SECRET_TOKEN):
                raise HTTPException(status_code=401, detail="Unauthorized")

        result = await dispatcher.feed_raw_update(bot=bot, update=payload)

        if isinstance(result, TelegramMethod):
            await dispatcher.silent_call_request(bot=bot, result=result)

        return JSONResponse(content={})

    return app


def run_webhook() -> None:
    uvicorn.run(app, host=WEBHOOK_HOST, port=WEBHOOK_PORT)


# Module-level ASGI application — used by Vercel and any other ASGI runner
# that imports this module directly (e.g. ``vercel`` serverless functions).
# In development (polling) mode this module is never imported, so there are
# no unwanted side-effects during local runs.
app = create_app()