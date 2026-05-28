import re

from aiogram import Bot, types
import traceback
from src.core.engine.registry import resolve_platform
from src.core.engine.manager import VideoManager
from src.core.engine.job_controller import job_controller
from src.bot.keyboards.builder import build_format_keyboard
from src.config.phrases import get_random_phrase
from src.config.settings import (
    DEFAULT_CAPTION,
    GROUP_NEED_ADMIN_MESSAGE,
    TELEGRAM_UPLOAD_TIMEOUT_SECONDS,
    TELEGRAM_MEDIA_GROUP_LIMIT,
    INSTAGRAM_TEMPORARILY_UNAVAILABLE_MESSAGE,
)
from src.core.uploaders.telegram import TelegramUploadSender
from src.core.platforms.base import MediaItem

import asyncio


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

async def handle_link(message: types.Message, bot: Bot):
    url = (message.text or "").strip()
    if not url:
        return

    is_group_chat = message.chat.type in {"group", "supergroup"}
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
    
    try:
        metadata = await manager.fetch_metadata()
        if not metadata:
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
        
        # Determine if we should show quality selection (e.g., YouTube only)
        if platform.name == "youtube" and metadata.get("extracted_formats"):
            temp_item = MediaItem(kind="video", formats=metadata.get("extracted_formats", []))
            keyboard = build_format_keyboard(temp_item, url)
            
            if status_msg:
                await status_msg.delete()
            if track_user_job:
                await job_controller.release(user_id)
            await message.answer(
                summary,
                reply_markup=keyboard
            )
        else:
            # Auto-download for Instagram/others
            # Wait for 5-second cooldown between downloads
            if track_user_job:
                await job_controller.wait_for_download_cooldown(user_id)
            if is_group_chat:
                media_items = await manager.download_media(metadata={})
                caption = None
            else:
                media_items = await manager.download_media(metadata=metadata)
                caption = DEFAULT_CAPTION
                if platform.name == "instagram":
                    caption_builder = getattr(manager.formatter, "build_caption", None)
                    if callable(caption_builder):
                        caption_builder(metadata)
            
            sender = TelegramUploadSender(
                message=message,
                status_message=status_msg,
                caption=caption,
                request_timeout=TELEGRAM_UPLOAD_TIMEOUT_SECONDS,
                media_group_limit=TELEGRAM_MEDIA_GROUP_LIMIT,
                reply_to_message_id=None if not is_group_chat else message.message_id,
            )
            await sender.send(media_items)
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
        print(f"Error handling link: {e}")
        traceback.print_exc()
        instagram_error = getattr(manager.downloader, "_last_error", None)
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
