"""Instagram media downloader: fetches metadata and resolves direct media URLs."""

import asyncio
import json
import logging
from datetime import datetime
from urllib.parse import unquote

import instaloader
import requests as _requests
from cachetools import TTLCache

from src.config.settings import INSTAGRAM_SESSIONID
from src.constants.limits import MAX_VIDEO_SIZE_BYTES
from src.core.platforms.base import (
    AbstractVideoDownloader,
    DownloadResult,
    InfoDict,
    MediaItem,
)
from src.core.platforms.instagram.data_extractor import InstagramDataExtractor
from src.core.platforms.instagram.file_helper import InstagramFileHelper
from src.core.platforms.instagram.session import InstagramSessionManager
from src.core.platforms.instagram.url_parser import InstagramUrlParser

logger = logging.getLogger(__name__)

# TTL of 10 minutes — Instagram CDN URLs expire, so stale cache entries would
# return dead links.
_CACHE_TTL = 600
_CACHE_MAX = 128


class InstagramDownloader(AbstractVideoDownloader):
    def __init__(
        self,
        video_limit_bytes: int = MAX_VIDEO_SIZE_BYTES,
        download_workers: int = 0,
    ) -> None:
        self.video_limit_bytes = video_limit_bytes

        self._metadata_cache: TTLCache = TTLCache(maxsize=_CACHE_MAX, ttl=_CACHE_TTL)
        self._post_cache: TTLCache = TTLCache(maxsize=_CACHE_MAX, ttl=_CACHE_TTL)
        self._download_cache: TTLCache = TTLCache(maxsize=_CACHE_MAX, ttl=_CACHE_TTL)

        self._session_manager = InstagramSessionManager()
        self._url_parser = InstagramUrlParser()
        self._data_extractor = InstagramDataExtractor()
        self._file_helper = InstagramFileHelper()

    @property
    def _last_error(self) -> str | None:
        return self._session_manager.last_error

    @_last_error.setter
    def _last_error(self, value: str | None) -> None:
        self._session_manager.last_error = value

    @property
    def loader(self) -> instaloader.Instaloader:
        return self._session_manager.loader

    @property
    def _session_loaded(self) -> bool:
        return self._session_manager.session_loaded

    async def fetch_metadata(self, url: str) -> InfoDict | None:
        if url in self._metadata_cache:
            return self._metadata_cache[url]

        if not self._session_manager.require_session():
            return None

        if "/stories/" in url:
            username, story_id = self._url_parser.extract_story_parts(url)
            if not username:
                return None
            info: InfoDict = {
                "id": story_id or username,
                "title": f"{username} - Story",
                "author_username": username,
                "posted_at": None,
                "duration": 0,
                "filesize_approx": None,
                "view_count": None,
                "comment_count": None,
                "like_count": None,
                "description": "",
                "thumbnail": None,
            }
            self._metadata_cache[url] = info
            return info

        shortcode = self._url_parser.extract_shortcode(url)
        if not shortcode:
            return None

        def _fetch():
            try:
                post = instaloader.Post.from_shortcode(self.loader.context, shortcode)
                self._last_error = None
                return self._data_extractor.build_metadata_from_post(
                    post, shortcode, self._file_helper.content_length
                )
            except Exception as exc:
                self._last_error = str(exc)
                logger.warning("Metadata fetch failed: %s", exc)
                return None

        info = await asyncio.to_thread(_fetch)
        if info:
            self._metadata_cache[url] = info
        return info

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

        if not self._session_manager.require_session():
            return DownloadResult(media_items=[], info=None)

        def _resolve():
            try:
                if "/stories/" in url:
                    return self._download_story_url(url)
                return self._download_post_url(url)
            except Exception as exc:
                self._last_error = str(exc)
                logger.error("Download failed: %s", exc)
                return DownloadResult(media_items=[], info=None)

        result = await asyncio.to_thread(_resolve)
        if result.media_items:
            self._download_cache[cache_key] = result
        return result

    def _download_post_url(self, url: str) -> DownloadResult:
        shortcode = self._url_parser.extract_shortcode(url)
        if not shortcode:
            return DownloadResult(media_items=[], info=None)

        post = self._post_cache.get(shortcode)
        if post is None:
            try:
                post = instaloader.Post.from_shortcode(self.loader.context, shortcode)
                self._last_error = None
            except Exception as exc:
                self._last_error = str(exc)
                raise
            self._post_cache[shortcode] = post

        try:
            media_items = self._data_extractor.build_post_media(post)
        except Exception:
            media_items = []

        if not media_items and post.is_video:
            try:
                video_path, cleanup = self._file_helper.download_post_to_temp_file(
                    self.loader, post
                )
                if video_path:
                    media_items = [
                        MediaItem(
                            kind="video",
                            stream=self._file_helper.stream_file(video_path, cleanup),
                            thumbnail_url=post.url,
                            width=getattr(post, "video_width", None),
                            height=getattr(post, "video_height", None),
                            duration=(
                                int(round(float(post.video_duration)))
                                if post.video_duration
                                else None
                            ),
                            title=f"Instagram - {post.shortcode}",
                            author=post.owner_username,
                        )
                    ]
                else:
                    cleanup.cleanup()
            except Exception as exc:
                self._last_error = str(exc)
                logger.error("Instagram video fallback failed: %s", exc)

        info = self._metadata_cache.get(url) or self._data_extractor.build_metadata_from_post(
            post, shortcode, self._file_helper.content_length
        )
        return DownloadResult(media_items=media_items, info=info)

    def _session_id(self) -> str | None:
        if INSTAGRAM_SESSIONID:
            return unquote(INSTAGRAM_SESSIONID)
        return self.loader.context._session.cookies.get("sessionid", domain=".instagram.com")

    _BROWSER_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "X-IG-App-ID": "936619743392459",
        "Accept": "*/*",
        "Referer": "https://www.instagram.com/",
    }

    def _resolve_userid(self, username: str) -> int:
        primary_exc: Exception | None = None

        try:
            profile = instaloader.Profile.from_username(self.loader.context, username)
            return profile.userid
        except Exception as exc:
            primary_exc = exc
            logger.warning(
                "Profile.from_username('%s') failed [%s]: %s",
                username, type(exc).__name__, exc,
            )

        # Fallback: web_profile_info with browser headers — Instagram rejects instaloader's
        # own User-Agent for api/v1 endpoints ("useragent mismatch")
        try:
            session_id = self._session_id()
            if session_id:
                resp = _requests.get(
                    "https://www.instagram.com/api/v1/users/web_profile_info/",
                    params={"username": username},
                    headers=self._BROWSER_HEADERS,
                    cookies={"sessionid": session_id},
                    timeout=30,
                )
                if resp.ok:
                    user_id = resp.json().get("data", {}).get("user", {}).get("id")
                    if user_id:
                        logger.info("Resolved user ID via web_profile_info: %s", user_id)
                        return int(user_id)
                else:
                    logger.warning(
                        "web_profile_info HTTP %s: %s", resp.status_code, resp.text[:200]
                    )
        except Exception as fallback_exc:
            logger.warning(
                "web_profile_info fallback failed [%s]: %s",
                type(fallback_exc).__name__, fallback_exc,
            )

        exc_type = type(primary_exc).__name__ if primary_exc else ""
        if "LoginRequired" in exc_type:
            raise RuntimeError(
                "Story-larni yuklab olish uchun Instagram sessiyasi talab etiladi."
            ) from primary_exc
        raise RuntimeError(
            f"@{username} profilini yuklab bo'lmadi. "
            "Hisob xususiy (private), mavjud emas, yoki Instagram sessiyasi eskirgan."
        ) from primary_exc

    def _fetch_story_nodes(self, userid: int) -> list[dict]:
        """Call the same GraphQL endpoint the browser uses for stories.

        instaloader's get_stories() hits this same endpoint but with its own
        User-Agent, which Instagram rejects with 400 "invalid request".
        """
        session_id = self._session_id()
        if not session_id:
            raise RuntimeError("Instagram sessiyasi topilmadi.")

        variables = json.dumps({"reel_ids": [userid], "precomposed_overlay": False})
        resp = _requests.get(
            "https://www.instagram.com/graphql/query",
            params={
                "query_hash": "303a4ae99711322310f25250d988f3b7",
                "variables": variables,
            },
            headers=self._BROWSER_HEADERS,
            cookies={"sessionid": session_id},
            timeout=30,
        )
        if not resp.ok:
            raise RuntimeError(f"Story API xatosi {resp.status_code}: {resp.text[:200]}")

        nodes: list[dict] = []
        for reel in (resp.json().get("data") or {}).get("reels_media", []):
            nodes.extend(reel.get("items", []))
        return nodes

    def _download_story_url(self, url: str) -> DownloadResult:
        username, story_id = self._url_parser.extract_story_parts(url)
        if not username:
            return DownloadResult(media_items=[], info=None)

        userid = self._resolve_userid(username)
        nodes = self._fetch_story_nodes(userid)

        media_items: list[MediaItem] = []
        story_found = False
        first_item_date: datetime | None = None

        for node in nodes:
            if story_id and str(node.get("id")) != story_id:
                continue

            story_found = True
            is_video = bool(node.get("is_video", False))
            display_url = node.get("display_url", "")

            if is_video:
                video_resources = node.get("video_resources", [])
                media_url = video_resources[0]["src"] if video_resources else display_url
            else:
                media_url = display_url

            dimensions = node.get("dimensions") or {}
            width = dimensions.get("width")
            height = dimensions.get("height")

            raw_duration = node.get("video_duration")
            duration = int(round(float(raw_duration))) if is_video and raw_duration else None

            taken_at = node.get("taken_at_timestamp")
            if taken_at and first_item_date is None:
                first_item_date = datetime.utcfromtimestamp(taken_at)

            media_items.append(
                MediaItem(
                    kind="video" if is_video else "photo",
                    url=media_url,
                    thumbnail_url=display_url,
                    width=width,
                    height=height,
                    duration=duration,
                    title=f"{username} - Story",
                    author=username,
                )
            )

        if story_id and not story_found:
            raise RuntimeError(
                "Story topilmadi. Story-lar 24 soat o'tgach o'chib ketadi, "
                "shuning uchun u muddati tugagan bo'lishi mumkin."
            )

        if story_id and media_items:
            media_items = media_items[:1]

        info: InfoDict = {
            "id": story_id or username,
            "title": f"{username} - Story",
            "author_username": username,
            "posted_at": first_item_date,
            "duration": media_items[0].duration or 0 if media_items else 0,
            "filesize_approx": None,
            "view_count": None,
            "comment_count": None,
            "like_count": None,
            "description": "",
            "thumbnail": media_items[0].thumbnail_url if media_items else None,
        }
        self._metadata_cache[url] = info
        return DownloadResult(media_items=media_items, info=info)
