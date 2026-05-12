import os

from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from src.bot.app import create_bot, create_dispatcher


WEBHOOK_PATH = os.getenv("TELEGRAM_WEBHOOK_PATH", "/telegram/webhook")
WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL")
WEBHOOK_SECRET_TOKEN = os.getenv("TELEGRAM_WEBHOOK_SECRET_TOKEN")
WEBHOOK_HOST = os.getenv("TELEGRAM_WEBHOOK_HOST", "0.0.0.0")
WEBHOOK_PORT = int(os.getenv("TELEGRAM_WEBHOOK_PORT", "8000"))


def create_app() -> web.Application:
    bot = create_bot()
    dispatcher = create_dispatcher()

    app = web.Application()

    async def on_startup(app: web.Application) -> None:
        if not WEBHOOK_URL:
            raise RuntimeError("TELEGRAM_WEBHOOK_URL is not set")

        await bot.set_webhook(
            url=WEBHOOK_URL,
            drop_pending_updates=True,
            secret_token=WEBHOOK_SECRET_TOKEN or None,
        )

    async def on_shutdown(app: web.Application) -> None:
        await bot.delete_webhook(drop_pending_updates=True)

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    handler = SimpleRequestHandler(
        dispatcher=dispatcher,
        bot=bot,
        secret_token=WEBHOOK_SECRET_TOKEN or None,
    )
    handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dispatcher)

    return app


def run_webhook() -> None:
    web.run_app(create_app(), host=WEBHOOK_HOST, port=WEBHOOK_PORT)