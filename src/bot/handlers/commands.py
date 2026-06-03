from aiogram import types


async def handle_start(message: types.Message) -> None:
    await message.answer("Salom, menga Instagram havolasini yuboring, men media faylni yuklab olib beraman.")


async def handle_help(message: types.Message) -> None:
    await message.answer(
        "<b>Buyruqlar:</b>\n"
        "/start - xush kelibsiz xabarini ko'rsatadi\n"
        "/help - yordam matnini ko'rsatadi\n\n"
        "Boshlash uchun qo'llab-quvvatlanadigan Instagram havolasini yuboring.\n"
        "Kerak bo'lsa, menga yozing: @akbarswe_bot"
    )