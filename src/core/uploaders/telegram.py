from aiogram import Bot
from aiogram.types import InputMediaPhoto, InputMediaVideo, Message, URLInputFile, InputMediaAudio

from src.core.platforms.base import MediaItem
from src.constants.telegram import HTML_PARSE_MODE
from src.utils.streaming import StreamingInputFile


class TelegramMediaSender:
    def __init__(
        self,
        bot: Bot,
        chat_id: int | str,
        caption: str | None = None,
        request_timeout: int = 900,
        media_group_limit: int = 10,
        reply_to_message_id: int | None = None,
    ) -> None:
        self._bot = bot
        self._chat_id = chat_id
        self._caption = caption
        self._request_timeout = request_timeout
        self._media_group_limit = media_group_limit
        self._reply_to_message_id = reply_to_message_id

    async def send(self, media_items: list[MediaItem]) -> list[Message]:
        chunks = list(self._iter_chunks(media_items))
        sent_messages: list[Message] = []

        for chunk in chunks:
            if len(chunk) == 1:
                sent_message = await self._send_single(chunk[0])
                if sent_message:
                    sent_messages.append(sent_message)
                continue

            media_group = [
                self._to_telegram_media(
                    item,
                    caption=self._caption if index == 0 else None,
                )
                for index, item in enumerate(chunk)
            ]
            group_messages = await self._bot.send_media_group(
                chat_id=self._chat_id,
                media=media_group,
                request_timeout=self._request_timeout,
                reply_to_message_id=self._reply_to_message_id,
            )
            sent_messages.extend(group_messages)

        return sent_messages

    async def _send_single(self, item: MediaItem) -> Message | None:
        media_input = self._build_media_input(item)

        if item.kind == "photo":
            result = await self._bot.send_photo(
                chat_id=self._chat_id,
                photo=media_input,
                caption=self._caption,
                parse_mode=HTML_PARSE_MODE,
                request_timeout=self._request_timeout,
                reply_to_message_id=self._reply_to_message_id,
            )
            return result
        
        if item.kind == "audio":
             result = await self._bot.send_audio(
                chat_id=self._chat_id,
                audio=media_input,
                caption=self._caption,
                title=item.title,
                performer=item.author,
                duration=item.duration,
                thumbnail=URLInputFile(item.thumbnail_url) if item.thumbnail_url else None,
                parse_mode=HTML_PARSE_MODE,
                request_timeout=self._request_timeout,
                reply_to_message_id=self._reply_to_message_id,
            )
             return result

        result = await self._bot.send_video(
            chat_id=self._chat_id,
            video=media_input,
            caption=self._caption,
            parse_mode=HTML_PARSE_MODE,
            supports_streaming=True,
            width=item.width,
            height=item.height,
            duration=item.duration,
            thumbnail=URLInputFile(item.thumbnail_url) if item.thumbnail_url else None,
            request_timeout=self._request_timeout,
            reply_to_message_id=self._reply_to_message_id,
        )
        return result

    def _to_telegram_media(
        self,
        item: MediaItem,
        caption: str | None = None,
    ) -> InputMediaPhoto | InputMediaVideo | InputMediaAudio:
        media_input = self._build_media_input(item)

        if item.kind == "photo":
            return InputMediaPhoto(media=media_input, caption=caption, parse_mode=HTML_PARSE_MODE)
        
        if item.kind == "audio":
            return InputMediaAudio(
                media=media_input, 
                caption=caption, 
                parse_mode=HTML_PARSE_MODE,
                title=item.title, 
                performer=item.author, 
                duration=item.duration,
                thumbnail=URLInputFile(item.thumbnail_url) if item.thumbnail_url else None
            )

        return InputMediaVideo(
            media=media_input,
            caption=caption,
            parse_mode=HTML_PARSE_MODE,
            supports_streaming=True,
            width=item.width,
            height=item.height,
            duration=item.duration,
            thumbnail=URLInputFile(item.thumbnail_url) if item.thumbnail_url else None
        )

    def _build_media_input(self, item: MediaItem):
        if getattr(item, "file_id", None):
            return item.file_id

        if item.stream:
            ext = "mp3" if item.kind == "audio" else "mp4"
            return StreamingInputFile(item.stream, filename=f"media_{int(time.time())}.{ext}")

        if item.url:
            return URLInputFile(item.url)

        return None

    def _iter_chunks(self, media_items: list[MediaItem]):
        for start in range(0, len(media_items), self._media_group_limit):
            yield media_items[start : start + self._media_group_limit]


class TelegramUploadSender(TelegramMediaSender):
    def __init__(
        self,
        message: Message,
        status_message: Message | None,
        caption: str | None,
        request_timeout: int,
        media_group_limit: int,
        reply_to_message_id: int | None = None,
    ) -> None:
        super().__init__(
            bot=message.bot,
            chat_id=message.chat.id,
            caption=caption,
            request_timeout=request_timeout,
            media_group_limit=media_group_limit,
            reply_to_message_id=reply_to_message_id,
        )
        self._message = message
        self._status_message = status_message

