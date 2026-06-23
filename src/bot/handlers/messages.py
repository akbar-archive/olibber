import re
import traceback

from aiogram import Bot, types
from src.core.engine.registry import resolve_platform
from src.core.engine.manager import VideoManager
from src.core.engine.job_controller import job_controller
from src.config.phrases import get_random_phrase
from src.config.settings import (
    DEFAULT_CAPTION,
    GROUP_NEED_ADMIN_MESSAGE,
    TELEGRAM_UPLOAD_TIMEOUT_SECONDS,
    TELEGRAM_MEDIA_GROUP_LIMIT,
    INSTAGRAM_TEMPORARILY_UNAVAILABLE_MESSAGE,
)
from src.core.uploaders.telegram import TelegramUploadSender
from src.bot.handlers.logger import TelegramLogger

_URL_PATTERN = re.compile(r"^https?://\S+$", re.IGNORECASE)


async def _is_bot_admin(bot: Bot, chat_id: int) -> bool:
    chat_member = await bot.get_chat_member(chat_id, bot.id)
    return chat_member.status in {"administrator", "creator"}


def _build_group_caption(message: types.Message, url: str) -> str:
    user = message.from_user
    first_name = user.first_name if user and user.first_name else ""
    last_name = user.last_name if user and user.last_name else ""
    user_id = user.id if user else 0
    return f'talab qildi: <a href="tg://user?id={user_id}">{first_name} {last_name}</a>'


async def _prepare_and_validate_url(message: types.Message, bot: Bot) -> tuple[str | None, bool]:
    text = (message.text or "").strip()
    if not text or not _URL_PATTERN.fullmatch(text):
        return None, False

    is_group_chat = message.chat.type in {"group", "supergroup"}
    return text, is_group_chat


async def _handle_lock_and_cooldown(
    user_id: int, message: types.Message, track_user_job: bool
) -> bool:
    if not track_user_job:
        return True

    can_proceed, remaining = await job_controller.acquire(user_id)
    if not can_proceed:
        if remaining > 0:
            await message.answer(
                f"Siz {remaining} soniyadan so'ng yana yuborishingiz mumkin"
            )
        else:
            await message.answer("Men hozir sizning so'rovingiz bilan bandman")
        return False

    return True


async def handle_link(message: types.Message, bot: Bot):
    url, is_group_chat = await _prepare_and_validate_url(message, bot)
    if not url:
        return

    platform = resolve_platform(url)
    if not platform:
        if not is_group_chat:
            await message.answer(
                "Bu havola qo'llab-quvvatlanmaydi. Faqat Instagram va YouTube havolalari ishlaydi.",
                reply_to_message_id=message.message_id,
            )
        return

    if is_group_chat and not await _is_bot_admin(bot, message.chat.id):
        await message.answer(
            GROUP_NEED_ADMIN_MESSAGE,
            reply_to_message_id=message.message_id,
        )
        return

    manager = VideoManager(url, platform)
    if not manager.is_valid_url():
        return

    user_id = message.from_user.id if message.from_user else 0
    status_msg: types.Message | None = None
    wait_for_response = not is_group_chat
    track_user_job = not is_group_chat

    if not await _handle_lock_and_cooldown(user_id, message, track_user_job):
        return

    logger = TelegramLogger(bot)

    if wait_for_response:
        status_msg = await message.answer(
            get_random_phrase(),
            reply_to_message_id=message.message_id,
        )
        await job_controller.set_waiting_message(user_id, status_msg.message_id)

    if track_user_job:
        await job_controller.set_pending_url(user_id, url)

    metadata = await manager.fetch_metadata()

    try:
        if not metadata:
            if not is_group_chat:
                if platform.name == "instagram":
                    if status_msg:
                        await status_msg.edit_text(
                            INSTAGRAM_TEMPORARILY_UNAVAILABLE_MESSAGE
                        )
                    else:
                        await message.answer(
                            INSTAGRAM_TEMPORARILY_UNAVAILABLE_MESSAGE,
                            reply_to_message_id=message.message_id,
                        )
                else:
                    if status_msg:
                        await status_msg.edit_text(
                            "❌ Metama'lumotlarni olishning imkoni bo'lmadi."
                        )
                    else:
                        await message.answer(
                            "❌ Metama'lumotlarni olishning imkoni bo'lmadi.",
                            reply_to_message_id=message.message_id,
                        )
            if track_user_job:
                await job_controller.release(user_id)
            return

        summary = manager.formatter.build_summary(metadata)

        if track_user_job:
            await job_controller.wait_for_download_cooldown(user_id)

        if is_group_chat:
            media_items = await manager.download_media(metadata=metadata)
            caption = _build_group_caption(message, url)
        else:
            media_items = await manager.download_media(metadata=metadata)
            caption = DEFAULT_CAPTION

        if not media_items:
            raise RuntimeError("No media items returned")

        sender = TelegramUploadSender(
            message=message,
            status_message=status_msg,
            caption=caption,
            request_timeout=TELEGRAM_UPLOAD_TIMEOUT_SECONDS,
            media_group_limit=TELEGRAM_MEDIA_GROUP_LIMIT,
            reply_to_message_id=None if not is_group_chat else message.message_id,
        )
        sent_messages = await sender.send(media_items)

        await logger.log_media(message, url, sent_messages)

        if wait_for_response and summary:
            await message.answer(
                summary,
                disable_web_page_preview=True,
            )
        if status_msg:
            await status_msg.delete()
        if track_user_job:
            await job_controller.release(user_id)

    except Exception as e:
        traceback.print_exc()
        instagram_error = getattr(manager.downloader, "_last_error", None)
        error_text = instagram_error or str(e)

        await logger.log_error(message, url, error_text)

        if not is_group_chat:
            if platform.name == "instagram":
                message_text = INSTAGRAM_TEMPORARILY_UNAVAILABLE_MESSAGE
                if instagram_error:
                    message_text = f"{message_text}\n\n{instagram_error}"
                if status_msg:
                    await status_msg.edit_text(message_text)
                else:
                    await message.answer(
                        message_text,
                        reply_to_message_id=message.message_id,
                    )
            else:
                if status_msg:
                    await status_msg.edit_text("❌ Kutilmagan xatolik yuz berdi.")
                else:
                    await message.answer(
                        "❌ Kutilmagan xatolik yuz berdi.",
                        reply_to_message_id=message.message_id,
                    )

        if track_user_job:
            await job_controller.release(user_id)

