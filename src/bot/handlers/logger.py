from html import escape
from urllib.parse import urlparse

from aiogram import Bot, types

from src.core.platforms.base import MediaItem
from src.core.uploaders.telegram import TelegramMediaSender
from src.constants.telegram import HTML_PARSE_MODE
from src.constants.groups import TARGET_GROUP_ID
from src.constants.logging import (
    LOG_MEDIA_CAPTION_URL_LABEL,
    LOG_MEDIA_CAPTION_NAME_LABEL,
    LOG_MEDIA_CAPTION_USER_LABEL,
)
from src.constants.limits import TELEGRAM_MEDIA_GROUP_LIMIT


class TelegramLogger:
    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    def build_log_caption(self, message: types.Message, source_url: str) -> str:
        user = message.from_user
        full_name = escape(user.full_name if user else "Unknown")
        user_id = user.id if user else 0
        parsed = urlparse(source_url)
        url_display = (
            escape(
                f"{parsed.netloc.removeprefix('www.')}{parsed.path.rstrip('/')}",
                quote=False,
            )
            if parsed.netloc and parsed.path
            else escape(source_url.rstrip("/"), quote=False)
        )
        url_href = escape(source_url, quote=True)
        return (
            f"{LOG_MEDIA_CAPTION_NAME_LABEL}: {full_name}\n"
            f'{LOG_MEDIA_CAPTION_USER_LABEL}: <a href="tg://user?id={user_id}">{user_id}</a>\n'
            f'{LOG_MEDIA_CAPTION_URL_LABEL}: <a href="{url_href}">{url_display}</a>'
        )

    def _extract_sent_media_file_id(
        self,
        sent_message: types.Message,
    ) -> tuple[str | None, str | None]:
        if sent_message.photo:
            return "photo", sent_message.photo[-1].file_id
        if sent_message.video:
            return "video", sent_message.video.file_id
        if sent_message.audio:
            return "audio", sent_message.audio.file_id
        return None, None

    async def log_media(
        self,
        source_message: types.Message,
        source_url: str,
        sent_messages: list[types.Message],
    ) -> None:
        if source_message.chat.id == TARGET_GROUP_ID:
            return

        media_items: list[MediaItem] = []
        for sent_message in sent_messages:
            media_kind, file_id = self._extract_sent_media_file_id(sent_message)
            if not media_kind or not file_id:
                continue
            media_items.append(
                MediaItem(
                    kind=media_kind,
                    url=None,
                    stream=None,
                    file_id=file_id,
                )
            )

        if not media_items:
            return

        caption = self.build_log_caption(source_message, source_url)

        sender = TelegramMediaSender(
            bot=self._bot,
            chat_id=TARGET_GROUP_ID,
            caption=caption,
            media_group_limit=TELEGRAM_MEDIA_GROUP_LIMIT,
        )
        await sender.send(media_items)

    async def log_error(
        self,
        source_message: types.Message,
        source_url: str,
        error_text: str,
    ) -> None:
        caption = self.build_log_caption(source_message, source_url)
        await self._bot.send_message(
            chat_id=TARGET_GROUP_ID,
            text=f"ERROR\n\n{caption}\n\n<blockquote>{escape(error_text)}</blockquote>",
            parse_mode=HTML_PARSE_MODE,
            disable_web_page_preview=True,
        )
