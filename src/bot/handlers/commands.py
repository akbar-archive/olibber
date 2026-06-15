from aiogram import types


async def handle_start(message: types.Message) -> None:
    await message.answer(
        "Salom! 👋\n\n"
        "Men Instagram rasmlar va videolarni yuklab beruvchi botman.\n"
        "Boshlash uchun /help buyrug'ini yuboring."
    )


async def handle_help(message: types.Message) -> None:
    await message.answer(
        "<b>📥 Olibber Bot</b>\n\n"
        "Bu bot Instagram havolalaridan rasm va videolarni yuklab beradi.\n\n"
        "<b>🛠 Buyruqlar:</b>\n"
        "/start — botni ishga tushirish\n"
        "/help — ushbu yordam xabarini ko'rish\n\n"
        "<b>📌 Qanday ishlatish kerak:</b>\n"
        "1. Instagram'dan post, reel havolasini nusxalang\n"
        "2. Havolani shu yerga yuboring\n"
        "3. Bot uni yuklab beradi\n\n"
        "<b>⚠️ Eslatma:</b>\n"
        "Faqat ochiq (public) akkauntlar ishlaydi.\n\n"
        "<b>🆘 Muammo bo'lsa:</b>\n"
        "@olibber_support_bot ga yozing",
    )