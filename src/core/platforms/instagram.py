import asyncio
import base64
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import AsyncIterable
from urllib.parse import urlparse, unquote
from urllib.request import Request, urlopen

import requests as _requests

import instaloader

from src.core.platforms.base import (
    AbstractLinkChecker,
    AbstractPlatform,
    AbstractVideoDownloader,
    AbstractVideoFormatter,
    DownloadResult,
    InfoDict,
    MediaItem
)
from src.config.settings import (
    INSTAGRAM_TEMPORARILY_UNAVAILABLE_MESSAGE,
    INSTAGRAM_USERNAME,
    INSTALOADER_SESSION_B64,
    INSTAGRAM_SESSIONID,
    MAX_VIDEO_SIZE_BYTES,
)


class InstagramSessionManager:
    def __init__(self) -> None:
        self.loader = instaloader.Instaloader(
            quiet=True,
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            save_metadata=False,
            compress_json=False,
            request_timeout=60.0,
        )
        self.session_loaded = False
        self.last_error: str | None = None
        if INSTALOADER_SESSION_B64 and INSTAGRAM_USERNAME:
            self.load_session_from_env()
        elif INSTAGRAM_SESSIONID:
            self.load_session_from_cookie(INSTAGRAM_SESSIONID)

    def load_session_from_env(self) -> None:
        try:
            decoded = base64.b64decode(INSTALOADER_SESSION_B64)
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".session")
            try:
                temp_file.write(decoded)
                temp_file.flush()
                temp_file.close()
                self.loader.load_session_from_file(INSTAGRAM_USERNAME, filename=temp_file.name)
                self.session_loaded = True
                self.last_error = None
            finally:
                try:
                    os.unlink(temp_file.name)
                except Exception:
                    pass
        except Exception as exc:
            self.last_error = f"Instagram sessiyasini yuklab bo'lmadi: {exc}"
            print("Failed to load Instagram session:", exc)

    def load_session_from_cookie(self, session_id: str) -> None:
        try:
            # URL-decode in case value came from env as %3A-encoded string
            session_id = unquote(session_id)
            # Set the sessionid cookie directly on the underlying requests.Session
            self.loader.context._session.cookies.set(
                "sessionid", session_id, domain=".instagram.com"
            )
            self.session_loaded = True
            self.last_error = None
            print("Instagram session loaded from INSTAGRAM_SESSIONID cookie.")
        except Exception as exc:
            self.last_error = f"INSTAGRAM_SESSIONID dan sessiya yuklab bo'lmadi: {exc}"
            print("Failed to load session from cookie:", exc)

    def require_session(self) -> bool:
        if self.session_loaded:
            return True
        self.last_error = "Instagram sessiyasi sozlanmagan. INSTAGRAM_SESSIONID yoki INSTALOADER_SESSION_B64 ni belgilang."
        print(self.last_error)
        return False


class InstagramUrlParser:
    @staticmethod
    def extract_shortcode(url: str) -> str | None:
        path_parts = [part for part in urlparse(url).path.split("/") if part]
        if len(path_parts) >= 2 and path_parts[0] in {"reel", "reels", "p", "tv"}:
            return path_parts[1]
        return None

    @staticmethod
    def extract_story_parts(url: str) -> tuple[str | None, str | None]:
        path_parts = [part for part in urlparse(url).path.split("/") if part]
        # stories/{username}/{story_id}
        if len(path_parts) >= 2 and path_parts[0] == "stories" and path_parts[1] != "highlights":
            username = path_parts[1]
            story_id = path_parts[2] if len(path_parts) >= 3 else None
            return username, story_id
        return None, None


class InstagramDataExtractor:
    @staticmethod
    def safe_video_url_from_node(node: dict | None) -> str | None:
        if not node:
            return None
        return node.get("video_url") or node.get("display_url")

    @staticmethod
    def safe_video_url(post: instaloader.Post) -> str | None:
        node = getattr(post, "_node", None)
        if isinstance(node, dict):
            video_url = node.get("video_url")
            if video_url:
                return video_url
        try:
            return post.video_url
        except Exception:
            return None

    @staticmethod
    def extract_dimensions(node: dict) -> tuple[int | None, int | None]:
        dimensions = node.get("dimensions") or {}
        width = dimensions.get("width")
        height = dimensions.get("height")

        if width and height:
            return int(width), int(height)

        display_resources = node.get("display_resources") or []
        if display_resources:
            best = display_resources[-1]
            width = best.get("config_width") or best.get("width")
            height = best.get("config_height") or best.get("height")
            if width and height:
                return int(width), int(height)

        video_resources = node.get("video_resources") or []
        if video_resources:
            best = video_resources[-1]
            width = best.get("config_width") or best.get("width")
            height = best.get("config_height") or best.get("height")
            if width and height:
                return int(width), int(height)

        return None, None

    def build_post_media(self, post: instaloader.Post) -> list[MediaItem]:
        media_items: list[MediaItem] = []
        
        if post.typename == "GraphSidecar":
            nodes: list[dict] = []
            try:
                edges = post._field("edge_sidecar_to_children", "edges")
                if any(
                    edge["node"].get("is_video") and "video_url" not in edge["node"]
                    for edge in edges
                ):
                    edges = post._full_metadata["edge_sidecar_to_children"]["edges"]
                nodes = [edge["node"] for edge in edges]
            except Exception:
                for node in post.get_sidecar_nodes():
                    nodes.append(
                        {
                            "id": getattr(node, "mediaid", None),
                            "is_video": node.is_video,
                            "video_url": node.video_url,
                            "display_url": node.display_url,
                        }
                    )
        else:
            nodes = [post._node]

        for node in nodes:
            if post.typename == "GraphSidecar":
                is_video = bool(node.get("is_video", False))
                media_url = node.get("video_url") if is_video else node.get("display_url")
                duration_raw = node.get("video_duration")
            else:
                is_video = post.is_video
                media_url = self.safe_video_url(post) if is_video else post.url
                duration_raw = post.video_duration

            if not media_url:
                continue

            width, height = self.extract_dimensions(node)

            media_items.append(
                MediaItem(
                    kind="video" if is_video else "photo",
                    url=media_url,
                    thumbnail_url=node.get("display_url") or post.url,
                    width=width,
                    height=height,
                    duration=int(round(float(duration_raw))) if is_video and duration_raw else None,
                    title=f"Instagram - {post.shortcode}",
                    author=post.owner_username
                )
            )

        return media_items

    def build_metadata_from_post(self, post: instaloader.Post, shortcode: str, content_length_func) -> InfoDict:
        view_count = None
        filesize_approx = None
        if post.is_video:
            view_count = post.video_view_count or post.video_play_count
            video_url = self.safe_video_url(post)
            if video_url:
                filesize_approx = content_length_func(video_url)

        return {
            "id": shortcode,
            "title": f"{post.owner_username} - {shortcode}",
            "author_username": post.owner_username,
            "posted_at": post.date_utc,
            "duration": post.video_duration or 0,
            "filesize_approx": filesize_approx,
            "view_count": view_count,
            "comment_count": post.comments,
            "like_count": post.likes,
            "description": post.caption or "",
            "thumbnail": post.url
        }


class InstagramFileHelper:
    _video_extensions = {".mp4", ".m4v", ".mov", ".webm"}

    @staticmethod
    def content_length(url: str) -> int | None:
        try:
            request = Request(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
                method="HEAD",
            )
            with urlopen(request, timeout=20) as response:
                raw = response.headers.get("Content-Length")
                return int(raw) if raw else None
        except Exception:
            return None

    @classmethod
    def _find_downloaded_video_file(cls, directory: str) -> str | None:
        candidates: list[Path] = []
        for root, _, files in os.walk(directory):
            for file_name in files:
                file_path = Path(root) / file_name
                if file_path.suffix.lower() in cls._video_extensions:
                    candidates.append(file_path)

        if not candidates:
            return None

        candidates.sort(key=lambda path: path.stat().st_size, reverse=True)
        return str(candidates[0])

    @staticmethod
    async def stream_file(file_path: str, cleanup: tempfile.TemporaryDirectory[str]) -> AsyncIterable[bytes]:
        try:
            with open(file_path, "rb") as file_handle:
                while True:
                    chunk = file_handle.read(65536)
                    if not chunk:
                        break
                    yield chunk
        finally:
            cleanup.cleanup()

    def download_post_to_temp_file(self, loader: instaloader.Instaloader, post: instaloader.Post) -> tuple[str | None, tempfile.TemporaryDirectory[str]]:
        temp_dir = tempfile.TemporaryDirectory()

        try:
            loader.download_post(post, target=temp_dir.name)
        except Exception:
            temp_dir.cleanup()
            raise

        return self._find_downloaded_video_file(temp_dir.name), temp_dir


class InstagramLinkChecker(AbstractLinkChecker):
    _pattern = re.compile(
        r"^(https?://)?(www\.)?instagram\.com/(reel|reels|p|tv|stories)/.+$"
    )

    def is_valid(self, url: str) -> bool:
        if not url or " " in url:
            return False
        return bool(self._pattern.match(url))


class InstagramDownloader(AbstractVideoDownloader):
    def __init__(
        self,
        video_limit_bytes: int = MAX_VIDEO_SIZE_BYTES,
        download_workers: int = 0,
    ) -> None:
        self.video_limit_bytes = video_limit_bytes
        self._metadata_cache: dict[str, InfoDict] = {}
        self._post_cache: dict[str, instaloader.Post] = {}
        self._download_cache: dict[str, DownloadResult] = {}
        self._cache_limit = 128

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

    def _trim_cache(self, cache: dict) -> None:
        while len(cache) > self._cache_limit:
            oldest_key = next(iter(cache))
            cache.pop(oldest_key, None)

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
                print("Metadata fetch failed:", exc)
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
                print("Download failed:", exc)
                return DownloadResult(media_items=[], info=None)

        result = await asyncio.to_thread(_resolve)
        if result.media_items:
            self._download_cache[cache_key] = result
            self._trim_cache(self._download_cache)
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
            self._trim_cache(self._post_cache)
        try:
            media_items = self._data_extractor.build_post_media(post)
        except Exception:
            media_items = []

        if not media_items and post.is_video:
            try:
                video_path, cleanup = self._file_helper.download_post_to_temp_file(self.loader, post)
                if video_path:
                    media_items = [
                        MediaItem(
                            kind="video",
                            stream=self._file_helper.stream_file(video_path, cleanup),
                            thumbnail_url=post.url,
                            width=getattr(post, "video_width", None),
                            height=getattr(post, "video_height", None),
                            duration=int(round(float(post.video_duration))) if post.video_duration else None,
                            title=f"Instagram - {post.shortcode}",
                            author=post.owner_username,
                        )
                    ]
                else:
                    cleanup.cleanup()
            except Exception as exc:
                self._last_error = str(exc)
                print("Instagram video fallback failed:", exc)

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
            print(f"Profile.from_username('{username}') failed [{type(exc).__name__}]: {exc}")

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
                        print(f"Resolved user ID via web_profile_info: {user_id}")
                        return int(user_id)
                else:
                    print(f"web_profile_info HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as fallback_exc:
            print(f"web_profile_info fallback failed [{type(fallback_exc).__name__}]: {fallback_exc}")

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


class InstagramPlatform(AbstractPlatform):
    name = "instagram"

    def supports(self, url: str) -> bool:
        return "instagram.com/" in url

    def create_link_checker(self) -> AbstractLinkChecker:
        return InstagramLinkChecker()

    def create_downloader(self) -> AbstractVideoDownloader:
        return InstagramDownloader()

    def create_formatter(self) -> AbstractVideoFormatter:
        from src.utils.formatter import InstagramFormatter
        return InstagramFormatter()

