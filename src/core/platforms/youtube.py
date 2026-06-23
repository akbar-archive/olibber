import asyncio
import re

import yt_dlp

from src.core.platforms.base import (
    AbstractLinkChecker,
    AbstractPlatform,
    AbstractVideoDownloader,
    AbstractVideoFormatter,
    DownloadResult,
    InfoDict,
    MediaItem,
)
from src.config.settings import MAX_VIDEO_SIZE_BYTES

_DEFAULT_FORMAT = "best[ext=mp4][height<=720]/best[ext=mp4]/18"


class YoutubeLinkChecker(AbstractLinkChecker):
    _pattern = re.compile(
        r"^(https?://)?(www\.)?(youtube\.com/(watch\?.*v=[\w-]+|shorts/[\w-]+|embed/[\w-]+)|youtu\.be/[\w-]+)"
    )

    def is_valid(self, url: str) -> bool:
        if not url or " " in url:
            return False
        return bool(self._pattern.match(url))


class YoutubeDownloader(AbstractVideoDownloader):
    def __init__(self, video_limit_bytes: int = MAX_VIDEO_SIZE_BYTES) -> None:
        self.video_limit_bytes = video_limit_bytes
        self._metadata_cache: dict[str, InfoDict] = {}
        self._download_cache: dict[str, DownloadResult] = {}
        self._cache_limit = 64
        self.last_error: str | None = None

    def _trim_cache(self, cache: dict) -> None:
        while len(cache) > self._cache_limit:
            cache.pop(next(iter(cache)), None)

    def _ydl_opts(self, **extra) -> dict:
        return {"quiet": True, "no_warnings": True, **extra}

    async def fetch_metadata(self, url: str) -> InfoDict | None:
        if url in self._metadata_cache:
            return self._metadata_cache[url]

        def _fetch():
            try:
                with yt_dlp.YoutubeDL(self._ydl_opts()) as ydl:
                    info = ydl.extract_info(url, download=False)
                if not info:
                    return None
                return {
                    "id": info.get("id"),
                    "title": info.get("title"),
                    "author_username": info.get("uploader") or info.get("channel"),
                    "channel_url": info.get("channel_url") or info.get("uploader_url"),
                    "posted_at": info.get("upload_date"),
                    "duration": info.get("duration"),
                    "filesize_approx": info.get("filesize_approx") or info.get("filesize"),
                    "view_count": info.get("view_count"),
                    "comment_count": info.get("comment_count"),
                    "like_count": info.get("like_count"),
                    "description": info.get("description", ""),
                    "thumbnail": info.get("thumbnail"),
                }
            except Exception as exc:
                self.last_error = str(exc)
                print("YouTube metadata fetch failed:", exc)
                return None

        result = await asyncio.to_thread(_fetch)
        if result:
            self._metadata_cache[url] = result
            self._trim_cache(self._metadata_cache)
        return result

    async def download_media(
        self,
        url: str,
        format_id: str | None = None,
        metadata: InfoDict | None = None,
    ) -> DownloadResult:
        cache_key = f"{url}:{format_id or ''}"
        if cache_key in self._download_cache:
            return self._download_cache[cache_key]

        metadata = metadata or await self.fetch_metadata(url)
        if not metadata:
            return DownloadResult(media_items=[], info=None)

        fmt = format_id or _DEFAULT_FORMAT

        def _resolve():
            try:
                with yt_dlp.YoutubeDL(self._ydl_opts(format=fmt)) as ydl:
                    info = ydl.extract_info(url, download=False)
                if not info:
                    self.last_error = "Video ma'lumotlarini olishda xatolik."
                    return DownloadResult(media_items=[], info=metadata)

                media_url = info.get("url")
                if not media_url:
                    self.last_error = "Video URL'ini olishda xatolik yuz berdi."
                    return DownloadResult(media_items=[], info=metadata)

                item = MediaItem(
                    kind="video",
                    url=media_url,
                    thumbnail_url=metadata.get("thumbnail"),
                    width=info.get("width"),
                    height=info.get("height"),
                    duration=int(info["duration"]) if info.get("duration") else metadata.get("duration"),
                    title=metadata.get("title"),
                    author=metadata.get("author_username"),
                )
                return DownloadResult(media_items=[item], info=metadata)
            except Exception as exc:
                self.last_error = str(exc)
                print("YouTube download failed:", exc)
                return DownloadResult(media_items=[], info=metadata)

        result = await asyncio.to_thread(_resolve)
        if result.media_items:
            self._download_cache[cache_key] = result
            self._trim_cache(self._download_cache)
        return result


class YoutubePlatform(AbstractPlatform):
    name = "youtube"

    def supports(self, url: str) -> bool:
        return "youtube.com/" in url or "youtu.be/" in url

    def create_link_checker(self) -> AbstractLinkChecker:
        return YoutubeLinkChecker()

    def create_downloader(self) -> AbstractVideoDownloader:
        return YoutubeDownloader()

    def create_formatter(self) -> AbstractVideoFormatter:
        from src.utils.formatter import YoutubeFormatter
        return YoutubeFormatter()
