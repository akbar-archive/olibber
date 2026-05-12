import asyncio
import logging
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VENV_SITE_PACKAGES = PROJECT_ROOT / ".venv" / "Lib" / "site-packages"

if VENV_SITE_PACKAGES.exists() and str(VENV_SITE_PACKAGES) not in sys.path:
    sys.path.insert(0, str(VENV_SITE_PACKAGES))

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import TOKEN
from src.bot.handlers.commands import handle_start, handle_help
from src.bot.handlers.messages import handle_link
from src.bot.handlers.callbacks import handle_callback
from src.bot.handlers.inline import handle_inline

async def main() -> None:
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # Register handlers
    dp.message.register(handle_start, CommandStart())
    dp.message.register(handle_help, Command("help"))
    dp.message.register(handle_link, F.text.regexp(r'https?://'))
    dp.callback_query.register(handle_callback)
    dp.inline_query.register(handle_inline)

    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped gracefully ✨")
