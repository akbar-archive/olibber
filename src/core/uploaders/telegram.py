import time
from aiogram.types import InputMediaPhoto, InputMediaVideo, Message, URLInputFile, InputMediaAudio

from src.core.platforms.base import MediaItem
from src.utils.streaming import StreamingInputFile


class TelegramUploadSender:
    def __init__(
        self,
        message: Message,
        status_message: Message,
        caption: str,
        request_timeout: int,
        media_group_limit: int,
    ):
        self._message = message
        self._status_message = status_message
        self._caption = caption
        self._request_timeout = request_timeout
        self._media_group_limit = media_group_limit

    async def send(self, media_items: list[MediaItem]) -> Message:
        chunks = list(self._iter_chunks(media_items))

        for chunk in chunks:
            if len(chunk) == 1:
                await self._send_single(chunk[0])
                continue

            media_group = [
                self._to_telegram_media(
                    item,
                    caption=self._caption if index == 0 else None,
                )
                for index, item in enumerate(chunk)
            ]
            await self._message.answer_media_group(
                media=media_group,
                request_timeout=self._request_timeout,
            )

        return self._status_message

    async def _send_single(self, item: MediaItem) -> Message | None:
        media_input = self._build_media_input(item)

        if item.kind == "photo":
            return await self._message.answer_photo(
                photo=media_input,
                caption=self._caption,
                request_timeout=self._request_timeout,
            )
        
        if item.kind == "audio":
             return await self._message.answer_audio(
                audio=media_input,
                caption=self._caption,
                title=item.title,
                performer=item.author,
                duration=item.duration,
                thumbnail=URLInputFile(item.thumbnail_url) if item.thumbnail_url else None,
                request_timeout=self._request_timeout,
            )

        return await self._message.answer_video(
            video=media_input,
            caption=self._caption,
            supports_streaming=True,
            width=item.width,
            height=item.height,
            duration=item.duration,
            thumbnail=URLInputFile(item.thumbnail_url) if item.thumbnail_url else None,
            request_timeout=self._request_timeout,
        )

    def _to_telegram_media(
        self,
        item: MediaItem,
        caption: str | None = None,
    ) -> InputMediaPhoto | InputMediaVideo | InputMediaAudio:
        media_input = self._build_media_input(item)

        if item.kind == "photo":
            return InputMediaPhoto(media=media_input, caption=caption)
        
        if item.kind == "audio":
            return InputMediaAudio(
                media=media_input, 
                caption=caption, 
                title=item.title, 
                performer=item.author, 
                duration=item.duration,
                thumbnail=URLInputFile(item.thumbnail_url) if item.thumbnail_url else None
            )

        return InputMediaVideo(
            media=media_input,
            caption=caption,
            supports_streaming=True,
            width=item.width,
            height=item.height,
            duration=item.duration,
            thumbnail=URLInputFile(item.thumbnail_url) if item.thumbnail_url else None
        )

    def _build_media_input(self, item: MediaItem):
        if item.stream:
            ext = "mp3" if item.kind == "audio" else "mp4"
            return StreamingInputFile(item.stream, filename=f"media_{int(time.time())}.{ext}")

        if item.url:
            return URLInputFile(item.url)

        return None

    def _iter_chunks(self, media_items: list[MediaItem]):
        for start in range(0, len(media_items), self._media_group_limit):
            yield media_items[start : start + self._media_group_limit]
