import os
import secrets
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from aiogram.methods.base import TelegramMethod
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from src.bot.app import create_bot, create_dispatcher


WEBHOOK_PATH = os.getenv("TELEGRAM_WEBHOOK_PATH", "/telegram/webhook")
WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL")
WEBHOOK_SECRET_TOKEN = os.getenv("TELEGRAM_WEBHOOK_SECRET_TOKEN")
WEBHOOK_HOST = os.getenv("TELEGRAM_WEBHOOK_HOST", "0.0.0.0")
WEBHOOK_PORT = int(os.getenv("TELEGRAM_WEBHOOK_PORT", "8000"))


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

        await dispatcher.emit_startup(**workflow_data)
        await bot.set_webhook(
            url=WEBHOOK_URL,
            drop_pending_updates=True,
            secret_token=WEBHOOK_SECRET_TOKEN or None,
        )

        yield

        await bot.delete_webhook(drop_pending_updates=True)
        await dispatcher.emit_shutdown(**workflow_data)
        await bot.session.close()

    app = FastAPI(lifespan=lifespan)

    @app.post(WEBHOOK_PATH)
    async def telegram_webhook(request: Request) -> JSONResponse:
        bot = request.app.state.bot
        dispatcher = request.app.state.dispatcher

        if WEBHOOK_SECRET_TOKEN:
            secret_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
            if not secrets.compare_digest(secret_token, WEBHOOK_SECRET_TOKEN):
                raise HTTPException(status_code=401, detail="Unauthorized")

        payload: dict[str, Any] = await request.json()
        result = await dispatcher.feed_raw_update(bot=bot, update=payload)

        if isinstance(result, TelegramMethod):
            await dispatcher.silent_call_request(bot=bot, result=result)

        return JSONResponse(content={})

    return app


def run_webhook() -> None:
    uvicorn.run(create_app(), host=WEBHOOK_HOST, port=WEBHOOK_PORT)