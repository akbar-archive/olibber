import logging

from aiogram import Bot, types

from src.bot.handlers.logger import TelegramLogger
from src.constants.limits import TELEGRAM_MEDIA_GROUP_LIMIT, TELEGRAM_UPLOAD_TIMEOUT_SECONDS
from src.constants.messages import DEFAULT_CAPTION
from src.core.engine.job_controller import job_controller
from src.core.platforms.base import AbstractPlatform
from src.core.uploaders.telegram import TelegramUploadSender
from src.services.ui_helper import UIHelper

logger = logging.getLogger(__name__)


class MediaProcessorService:
    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self.telegram_logger = TelegramLogger(bot)

    def _build_group_caption(self, message: types.Message, url: str) -> str:
        user = message.from_user
        first_name = user.first_name if user and user.first_name else ""
        last_name = user.last_name if user and user.last_name else ""
        user_id = user.id if user else 0
        return f'talab qildi: <a href="tg://user?id={user_id}">{first_name} {last_name}</a>'

    async def process_request(
        self,
        message: types.Message,
        url: str,
        platform: AbstractPlatform,
        is_group_chat: bool,
        track_user_job: bool,
    ) -> None:
        user_id = message.from_user.id if message.from_user else 0
        status_msg: types.Message | None = None

        if not is_group_chat:
            status_msg = await UIHelper.send_loading_message(message)
            if track_user_job:
                await job_controller.set_waiting_message(user_id, status_msg.message_id)

        try:
            downloader = platform.create_downloader()
            formatter = platform.create_formatter()

            metadata = await downloader.fetch_metadata(url)
            if not metadata:
                if not is_group_chat:
                    if platform.name == "instagram":
                        await UIHelper.update_status_instagram_error(status_msg, message)
                    else:
                        await UIHelper.update_status_error(
                            status_msg, message, "❌ Metama'lumotlarni olishning imkoni bo'lmadi."
                        )
                return

            summary = formatter.build_summary(metadata)

            if track_user_job:
                await job_controller.wait_for_download_cooldown(user_id)

            download_result = await downloader.download_media(url, metadata=metadata)
            media_items = download_result.media_items

            if not media_items:
                raise RuntimeError("Hech qanday media olinmadi.")

            caption = self._build_group_caption(message, url) if is_group_chat else DEFAULT_CAPTION

            sender = TelegramUploadSender(
                message=message,
                status_message=status_msg,
                caption=caption,
                request_timeout=TELEGRAM_UPLOAD_TIMEOUT_SECONDS,
                media_group_limit=TELEGRAM_MEDIA_GROUP_LIMIT,
                reply_to_message_id=message.message_id if is_group_chat else None,
            )
            sent_messages = await sender.send(media_items)

            await self.telegram_logger.log_media(message, url, sent_messages)

            if not is_group_chat and summary:
                await message.answer(summary, disable_web_page_preview=True)

            if status_msg:
                await status_msg.delete()

        except Exception as exc:
            logger.exception("Error processing link '%s': %s", url, exc)
            platform_error = getattr(downloader, "_last_error", None) if "downloader" in locals() else None
            error_text = platform_error or str(exc)

            await self.telegram_logger.log_error(message, url, error_text)

            if not is_group_chat:
                if platform.name == "instagram":
                    await UIHelper.update_status_instagram_error(status_msg, message, platform_error)
                else:
                    await UIHelper.update_status_error(status_msg, message, "❌ Kutilmagan xatolik yuz berdi.")
        finally:
            if track_user_job:
                await job_controller.release(user_id)
