import asyncio
import os

from src.bot.polling import run_polling
from src.bot.webhook import run_webhook


def is_development() -> bool:
    env_value = os.getenv("ENVIRONMENT", "").strip().lower()
    return env_value in {"dev", "development", "local", "polling"}


def run_bot() -> None:
    if is_development():
        asyncio.run(run_polling())
    else:
        run_webhook()