import re
import asyncio
from urllib.parse import parse_qs, urlparse

import yt_dlp

from src.core.platforms.base import (
    AbstractLinkChecker,
    AbstractPlatform,
    AbstractVideoDownloader,
    AbstractVideoFormatter,
    DownloadResult,
    InfoDict,
    MediaItem,
    MediaFormat
)
from src.config.settings import MAX_VIDEO_SIZE_BYTES
from src.utils.streaming import stream_subprocess


class YouTubeLinkChecker(AbstractLinkChecker):
    _id_pattern = re.compile(r"^[\w-]{6,}$")

    def is_valid(self, url: str) -> bool:
        if not url or " " in url:
            return False

        parsed = urlparse(url if "://" in url else f"https://{url}")
        host = parsed.netloc.lower().removeprefix("www.")
        path = parsed.path

        if host == "youtu.be":
            video_id = path.strip("/")
            return bool(video_id and self._id_pattern.match(video_id))

        if host == "youtube.com":
            if path == "/watch":
                params = parse_qs(parsed.query)
                video_id = params.get("v", [""])[0]
                return bool(video_id and self._id_pattern.match(video_id))

            if path.startswith("/shorts/"):
                video_id = path.split("/", 3)[2]
                return bool(video_id and self._id_pattern.match(video_id))

        return False


class YouTubeDownloader(AbstractVideoDownloader):
    def __init__(self, video_limit_bytes: int = MAX_VIDEO_SIZE_BYTES):
        self.video_limit_bytes = video_limit_bytes
        self._metadata_cache: dict[str, InfoDict] = {}

    @staticmethod
    def _enrich_info(info: InfoDict) -> InfoDict:
        author_username = (
            info.get("uploader_id")
            or info.get("channel_id")
            or info.get("uploader")
        )
        if isinstance(author_username, str):
            author_username = author_username.lstrip("@")

        info["author_username"] = author_username
        info["posted_at"] = info.get("timestamp") or info.get("upload_date")
        
        formats = []
        for f in info.get("formats", []):
            if f.get("vcodec") != "none" and f.get("acodec") != "none":
                formats.append(MediaFormat(
                    format_id=f["format_id"],
                    extension=f["ext"],
                    resolution=f.get("format_note") or f.get("resolution"),
                    filesize=f.get("filesize") or f.get("filesize_approx"),
                    vcodec=f.get("vcodec"),
                    acodec=f.get("acodec"),
                    is_video=True
                ))
            elif f.get("vcodec") == "none" and f.get("acodec") != "none":
                formats.append(MediaFormat(
                    format_id=f["format_id"],
                    extension=f["ext"],
                    resolution="Audio",
                    filesize=f.get("filesize") or f.get("filesize_approx"),
                    vcodec=None,
                    acodec=f.get("acodec"),
                    is_video=False
                ))
        
        info["extracted_formats"] = formats
        return info

    async def fetch_metadata(self, url: str) -> InfoDict | None:
        if url in self._metadata_cache:
            return self._metadata_cache[url]

        ydl_opts = {
            "skip_download": True,
            "noplaylist": True,
            "ignoreconfig": True,
        }

        def _fetch():
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                return self._enrich_info(info)
            except Exception as exc:
                print("Metadata fetch failed:", exc)
                return None

        enriched = await asyncio.to_thread(_fetch)
        if enriched:
            self._metadata_cache[url] = enriched
        return enriched

    async def download_media(self, url: str, format_id: str | None = None) -> DownloadResult:
        metadata = await self.fetch_metadata(url)
        if not metadata:
            return DownloadResult(media_items=[], info=None)

        if not format_id:
            format_id = "best"

        # Check if format_id is audio-only
        is_audio = False
        if format_id != "best":
            for f in metadata.get("extracted_formats", []):
                if f.format_id == format_id and not f.is_video:
                    is_audio = True
                    break

        # YouTube streaming
        cmd = ["yt-dlp", "-f", format_id, "-o", "-", url]
        stream = stream_subprocess(cmd)
        
        media_item = MediaItem(
            kind="audio" if is_audio else "video",
            stream=stream,
            thumbnail_url=metadata.get("thumbnail"),
            width=metadata.get("width"),
            height=metadata.get("height"),
            duration=int(round(float(metadata.get("duration")))) if metadata.get("duration") else None,
            title=metadata.get("title"),
            author=metadata.get("author_username"),
            formats=metadata.get("extracted_formats", [])
        )
        
        return DownloadResult(media_items=[media_item], info=metadata)


class YouTubePlatform(AbstractPlatform):
    name = "youtube"

    def supports(self, url: str) -> bool:
        return "youtube.com" in url or "youtu.be" in url

    def create_link_checker(self) -> AbstractLinkChecker:
        return YouTubeLinkChecker()

    def create_downloader(self) -> AbstractVideoDownloader:
        return YouTubeDownloader()

    def create_formatter(self) -> AbstractVideoFormatter:
        from src.utils.formatter import YouTubeFormatter
        return YouTubeFormatter()
