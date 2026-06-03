import re
from html import escape
from urllib.parse import urlparse

from aiogram import Bot, types
import traceback
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

from src.constants.groups import (
    GROUP_CAPTION_IG_LABEL,
    GROUP_CAPTION_TITLE,
    GROUP_CAPTION_USER_LABEL,
    TARGET_GROUP_ID,
)
from src.constants.telegram import HTML_PARSE_MODE
from src.constants.logging import (
    LOG_MEDIA_CAPTION_INSTAGRAM_LABEL,
    LOG_MEDIA_CAPTION_NAME_LABEL,
    LOG_MEDIA_CAPTION_USER_LABEL,
)
_GROUP_INSTAGRAM_LINK_ONLY_PATTERN = re.compile(
    r"^https?://(?:www\.)?instagram\.com/\S+$",
    re.IGNORECASE,
)


def _extract_group_instagram_link(text: str | None) -> str | None:
    if not text:
        return None

    candidate = text.strip()
    if not _GROUP_INSTAGRAM_LINK_ONLY_PATTERN.fullmatch(candidate):
        return None

    return candidate


async def _is_bot_admin(bot: Bot, chat_id: int) -> bool:
    chat_member = await bot.get_chat_member(chat_id, bot.id)
    return chat_member.status in {"administrator", "creator"}


def _build_group_caption(message: types.Message, url: str) -> str:
    user = message.from_user
    full_name = user.full_name if user else "Unknown"
    user_id = user.id if user else 0
    parsed = urlparse(url)
    ig_link_text = f"{parsed.netloc}{parsed.path}" if parsed.netloc and parsed.path else url

    return (
        f"{GROUP_CAPTION_TITLE}: {full_name}\n"
        f"{GROUP_CAPTION_USER_LABEL}<a href=\"tg://user?id={user_id}\">{user_id}</a>\n"
        f"{GROUP_CAPTION_IG_LABEL}: <a href=\"{url}\">{ig_link_text}</a>"
    )


def _extract_sent_media_file_id(sent_message: types.Message) -> tuple[str | None, str | None]:
    if sent_message.photo:
        return "photo", sent_message.photo[-1].file_id
    if sent_message.video:
        return "video", sent_message.video.file_id
    if sent_message.audio:
        return "audio", sent_message.audio.file_id
    return None, None


def _build_log_caption(message: types.Message, instagram_url: str) -> str:
    user = message.from_user
    full_name = escape(user.full_name if user else "Unknown")
    user_id = user.id if user else 0
    parsed = urlparse(instagram_url)
    instagram_display = (
        escape(f"{parsed.netloc.removeprefix('www.')}{parsed.path.rstrip('/')}", quote=False)
        if parsed.netloc and parsed.path
        else escape(instagram_url.rstrip('/'), quote=False)
    )
    instagram_href = escape(instagram_url, quote=True)
    return (
        f"{LOG_MEDIA_CAPTION_NAME_LABEL}: {full_name}\n"
        f"{LOG_MEDIA_CAPTION_USER_LABEL}: <a href=\"tg://user?id={user_id}\">{user_id}</a>\n"
        f"{LOG_MEDIA_CAPTION_INSTAGRAM_LABEL}: <a href=\"{instagram_href}\">{instagram_display}</a>"
    )


async def _send_log_copy(
    bot: Bot,
    source_message: types.Message,
    instagram_url: str,
    sent_messages: list[types.Message],
) -> None:
    if source_message.chat.id == TARGET_GROUP_ID:
        return

    for sent_message in sent_messages:
        media_kind, file_id = _extract_sent_media_file_id(sent_message)
        if not media_kind or not file_id:
            continue

        caption = _build_log_caption(source_message, instagram_url)

        if media_kind == "photo":
            await bot.send_photo(
                chat_id=TARGET_GROUP_ID,
                photo=file_id,
                caption=caption,
                parse_mode=HTML_PARSE_MODE,
            )
        elif media_kind == "video":
            await bot.send_video(
                chat_id=TARGET_GROUP_ID,
                video=file_id,
                caption=caption,
                parse_mode=HTML_PARSE_MODE,
                supports_streaming=True,
            )
        elif media_kind == "audio":
            await bot.send_audio(
                chat_id=TARGET_GROUP_ID,
                audio=file_id,
                caption=caption,
                parse_mode=HTML_PARSE_MODE,
            )


async def _send_log_error_copy(
    bot: Bot,
    source_message: types.Message,
    instagram_url: str,
    error_text: str,
) -> None:
    caption = _build_log_caption(source_message, instagram_url)
    await bot.send_message(
        chat_id=TARGET_GROUP_ID,
        text=f"ERROR\n\n{caption}\n\n<blockquote>{escape(error_text)}</blockquote>",
        parse_mode=HTML_PARSE_MODE,
        disable_web_page_preview=True,
    )

async def handle_link(message: types.Message, bot: Bot):
    url = (message.text or "").strip()
    if not url:
        return

    is_group_chat = message.chat.type in {"group", "supergroup"}
    is_target_group = message.chat.id == TARGET_GROUP_ID
    if is_group_chat:
        url = _extract_group_instagram_link(url)
        if not url:
            return

        if not await _is_bot_admin(bot, message.chat.id):
            await message.answer(
                GROUP_NEED_ADMIN_MESSAGE,
                reply_to_message_id=message.message_id,
            )
            return

    platform = resolve_platform(url)
    if not platform:
        return

    manager = VideoManager(url, platform)
    if not manager.is_valid_url():
        return

    user_id = message.from_user.id if message.from_user else 0
    status_msg: types.Message | None = None
    wait_for_response = not is_group_chat
    track_user_job = not is_group_chat
    
    if track_user_job:
        # Check if user is already processing a request
        can_proceed, remaining = await job_controller.acquire(user_id)
        if not can_proceed:
            if remaining > 0:
                await message.answer(f"Siz {remaining} soniyadan so'ng yana yuborishingiz mumkin")
            else:
                # User is busy, send a "busy" duplicate request message
                await message.answer("Men hozir sizning so'rovingiz bilan bandman")
            return

    if wait_for_response:
        # Keep the private chat feedback, but stay silent in groups.
        status_msg = await message.answer(
            get_random_phrase(),
            reply_to_message_id=message.message_id,
        )
        await job_controller.set_waiting_message(user_id, status_msg.message_id)

    
    # Store the URL for the callback handler
    if track_user_job:
        await job_controller.set_pending_url(user_id, url)

    metadata = await manager.fetch_metadata()
    
    try:
        if not metadata:
            if not is_group_chat:
                if platform.name == "instagram":
                    if status_msg:
                        await status_msg.edit_text(INSTAGRAM_TEMPORARILY_UNAVAILABLE_MESSAGE)
                    else:
                        await message.answer(
                            INSTAGRAM_TEMPORARILY_UNAVAILABLE_MESSAGE,
                            reply_to_message_id=message.message_id,
                        )
                else:
                    if status_msg:
                        await status_msg.edit_text("❌ Metama'lumotlarni olishning imkoni bo'lmadi.")
                    else:
                        await message.answer(
                            "❌ Metama'lumotlarni olishning imkoni bo'lmadi.",
                            reply_to_message_id=message.message_id,
                        )
            if track_user_job:
                await job_controller.release(user_id)
            return

        summary = manager.formatter.build_summary(metadata)

        # Auto-download for supported platforms.
        if track_user_job:
            await job_controller.wait_for_download_cooldown(user_id)

        if is_group_chat:
            media_items = await manager.download_media(metadata=metadata)
            caption = _build_group_caption(message, url) if is_target_group else None
        else:
            media_items = await manager.download_media(metadata=metadata)
            caption = DEFAULT_CAPTION
            if platform.name == "instagram":
                caption_builder = getattr(manager.formatter, "build_caption", None)
                if callable(caption_builder):
                    maybe_caption = caption_builder(metadata)
                    if maybe_caption:
                        caption = maybe_caption

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
        await _send_log_copy(bot, message, url, sent_messages)
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
        await _send_log_error_copy(bot, message, url, error_text)
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
