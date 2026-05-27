from aiogram import types
import traceback
from src.core.engine.registry import resolve_platform
from src.core.engine.manager import VideoManager
from src.core.engine.job_controller import job_controller
from src.bot.keyboards.builder import build_format_keyboard
from src.config.phrases import get_random_phrase
from src.config.settings import (
    DEFAULT_CAPTION,
    TELEGRAM_UPLOAD_TIMEOUT_SECONDS,
    TELEGRAM_MEDIA_GROUP_LIMIT,
    INSTAGRAM_TEMPORARILY_UNAVAILABLE_MESSAGE,
)
from src.core.uploaders.telegram import TelegramUploadSender
from src.core.platforms.base import MediaItem

import asyncio

async def handle_link(message: types.Message):
    url = (message.text or "").strip()
    if not url:
        return

    platform = resolve_platform(url)
    if not platform:
        return

    manager = VideoManager(url, platform)
    if not manager.is_valid_url():
        return

    user_id = message.from_user.id if message.from_user else 0
    
    # Check if user is already processing a request
    can_proceed, remaining = await job_controller.acquire(user_id)
    if not can_proceed:
        if remaining > 0:
            await message.answer(f"Siz {remaining} soniyadan so'ng yana yuborishingiz mumkin")
        else:
            # User is busy, send a "busy" duplicate request message
            await message.answer("Men hozir sizning so'rovingiz bilan bandman")
        return

    # Send waiting message immediately for all link types
    status_msg = await message.answer(get_random_phrase())
    await job_controller.set_waiting_message(user_id, status_msg.message_id)
    
    # Store the URL for the callback handler
    await job_controller.set_pending_url(user_id, url)
    
    try:
        metadata = await manager.fetch_metadata()
        if not metadata:
            if platform.name == "instagram":
                await status_msg.edit_text(INSTAGRAM_TEMPORARILY_UNAVAILABLE_MESSAGE)
            else:
                await status_msg.edit_text("❌ Metama'lumotlarni olishning imkoni bo'lmadi.")
            await job_controller.release(user_id)
            return

        summary = manager.formatter.build_summary(metadata)
        
        # Determine if we should show quality selection (e.g., YouTube only)
        if platform.name == "youtube" and metadata.get("extracted_formats"):
            temp_item = MediaItem(kind="video", formats=metadata.get("extracted_formats", []))
            keyboard = build_format_keyboard(temp_item, url)
            
            await status_msg.delete()
            await job_controller.release(user_id)
            await message.answer(
                summary,
                reply_markup=keyboard
            )
        else:
            # Auto-download for Instagram/others
            # Wait for 5-second cooldown between downloads
            await job_controller.wait_for_download_cooldown(user_id)
            media_items = await manager.download_media(metadata=metadata)
            
            sender = TelegramUploadSender(
                message=message,
                status_message=status_msg,
                caption=DEFAULT_CAPTION,
                request_timeout=TELEGRAM_UPLOAD_TIMEOUT_SECONDS,
                media_group_limit=TELEGRAM_MEDIA_GROUP_LIMIT
            )
            await sender.send(media_items)
            if summary:
                await message.answer(summary, disable_web_page_preview=True)
            await status_msg.delete()
            
            await job_controller.release(user_id)

    except Exception as e:
        print(f"Error handling link: {e}")
        traceback.print_exc()
        instagram_error = getattr(manager.downloader, "_last_error", None)
        if platform.name == "instagram":
            message_text = INSTAGRAM_TEMPORARILY_UNAVAILABLE_MESSAGE
            if instagram_error:
                message_text = f"{message_text}\n\n{instagram_error}"
            await status_msg.edit_text(message_text)
        else:
            await status_msg.edit_text("❌ Kutilmagan xatolik yuz berdi.")
        await job_controller.release(user_id)
