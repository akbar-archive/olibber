from src.bot.app import create_bot, create_dispatcher


async def run_polling() -> None:
    bot = create_bot()
    dispatcher = create_dispatcher()

    await dispatcher.start_polling(bot)