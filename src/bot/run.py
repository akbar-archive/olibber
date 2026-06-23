import os
import asyncio


def is_development() -> bool:
    if os.getenv("VERCEL") == "1":
        return False
    env_value = os.getenv("ENVIRONMENT", "").strip().lower()
    if env_value in {"prod", "production", "webhook"}:
        return False
    return True


def run_bot() -> None:
    if is_development():
        from src.bot.polling import run_polling
        asyncio.run(run_polling())
    else:
        from src.bot.webhook import run_webhook
        run_webhook()