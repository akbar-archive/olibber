from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart

from src.bot.handlers.commands import router as commands_router
from src.bot.handlers.group_membership import router as group_membership_router
from src.bot.handlers.inline import router as inline_router
from src.bot.handlers.messages import router as messages_router
from src.constants.limits import TELEGRAM_UPLOAD_TIMEOUT_SECONDS
from src.config.settings import TOKEN


def create_bot() -> Bot:
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

    session = AiohttpSession(timeout=TELEGRAM_UPLOAD_TIMEOUT_SECONDS)
    return Bot(
        token=TOKEN, 
        session=session, 
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )


def create_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher()

    dispatcher.include_router(commands_router)
    dispatcher.include_router(group_membership_router)
    dispatcher.include_router(inline_router)
    dispatcher.include_router(messages_router)

    return dispatcher