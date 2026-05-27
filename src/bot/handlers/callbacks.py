from aiogram import types, F
from aiogram.exceptions import TelegramBadRequest
import traceback
from src.core.engine.job_controller import job_controller
from src.core.engine.registry import resolve_platform
from src.core.engine.manager import VideoManager
from src.core.uploaders.telegram import TelegramUploadSender
from src.config.settings import DEFAULT_CAPTION, TELEGRAM_UPLOAD_TIMEOUT_SECONDS, TELEGRAM_MEDIA_GROUP_LIMIT
from src.config.phrases import get_random_phrase

async def handle_callback(callback: types.CallbackQuery):
    if not callback.data.startswith("dl:"):
        return

    # dl:v:format_id or dl:a:format_id
    parts = callback.data.split(":")
    kind_code = parts[1]
    format_id = parts[2]
    
    user_id = callback.from_user.id
    url = await job_controller.get_pending_url(user_id)
    
    if not url:
        await callback.answer("❌ Kech qoldingiz. Iltimos, havolani qayta yuboring.", show_alert=True)
        return

    platform = resolve_platform(url)
    manager = VideoManager(url, platform)
    
    # Check if user is already processing a request
    can_proceed, remaining = await job_controller.acquire(user_id)
    if not can_proceed:
        if remaining > 0:
            await callback.message.answer(f"Siz {remaining} soniyadan so'ng yana yuborishingiz mumkin")
        else:
            # User is busy, send a "busy" duplicate request message
            await callback.message.answer("Men hozir sizning so'rovingiz bilan bandman")
        await callback.answer()
        return
    
    # Wait for 5-second cooldown between downloads
    # send a waiting message early so we can update it on error
    waiting_msg = await callback.message.answer(get_random_phrase())
    await job_controller.set_waiting_message(user_id, waiting_msg.message_id)

    await job_controller.wait_for_download_cooldown(user_id)

    try:
        media_items = await manager.download_media(format_id=format_id)

        sender = TelegramUploadSender(
            message=callback.message,
            status_message=callback.message,
            caption=DEFAULT_CAPTION,
            request_timeout=TELEGRAM_UPLOAD_TIMEOUT_SECONDS,
            media_group_limit=TELEGRAM_MEDIA_GROUP_LIMIT
        )

        await sender.send(media_items)
        await waiting_msg.delete()
        await job_controller.release(user_id)

    except Exception as e:
        print(f"Callback error: {e}")
        traceback.print_exc()
        instagram_error = getattr(manager.downloader, "_last_error", None)
        try:
            message_text = "❌ Yuklab olish muvaffaqiyatsiz tugadi."
            if instagram_error:
                message_text = f"{message_text}\n\n{instagram_error}"
            await waiting_msg.edit_text(message_text)
        except Exception:
            fallback_text = "❌ Yuklab olish muvaffaqiyatsiz tugadi."
            if instagram_error:
                fallback_text = f"{fallback_text}\n\n{instagram_error}"
            await callback.message.edit_text(fallback_text)
        await job_controller.release(user_id)

    try:
        await callback.answer()
    except TelegramBadRequest:
        # callback query may be too old or already answered; ignore to avoid crashing
        pass
