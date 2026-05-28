from aiogram import Bot, types

from src.config.settings import GROUP_NEED_ADMIN_MESSAGE


async def handle_my_chat_member(update: types.ChatMemberUpdated, bot: Bot) -> None:
    chat = update.chat
    if chat.type not in {"group", "supergroup"}:
        return

    old_status = update.old_chat_member.status
    new_status = update.new_chat_member.status

    if old_status not in {"left", "kicked"}:
        return

    if new_status in {"administrator", "creator"}:
        return

    await bot.send_message(chat.id, GROUP_NEED_ADMIN_MESSAGE)