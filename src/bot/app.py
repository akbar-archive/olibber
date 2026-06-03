from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart

from src.bot.handlers.commands import handle_help, handle_start
from src.bot.handlers.group_membership import handle_my_chat_member
from src.bot.handlers.inline import handle_inline
from src.bot.handlers.messages import handle_link
from src.config.settings import TOKEN


def create_bot() -> Bot:
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

    return Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


def create_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher()

    dispatcher.message.register(handle_start, CommandStart())
    dispatcher.message.register(handle_help, Command("help"))
    dispatcher.message.register(handle_link, F.text.regexp(r"https?://"))
    dispatcher.inline_query.register(handle_inline)
    dispatcher.my_chat_member.register(handle_my_chat_member)

    return dispatcher