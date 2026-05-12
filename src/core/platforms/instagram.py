import re
import asyncio
from urllib.parse import urlparse
from urllib.request import Request, urlopen

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
from src.config.settings import MAX_VIDEO_SIZE_BYTES


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
    ):
        self.video_limit_bytes = video_limit_bytes
        self._metadata_cache: dict[str, InfoDict] = {}
        self.loader = instaloader.Instaloader(
            quiet=True,
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            save_metadata=False,
            compress_json=False,
            request_timeout=60.0,
        )

    @staticmethod
    def _content_length(url: str) -> int | None:
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

    @staticmethod
    def _extract_shortcode(url: str) -> str | None:
        path_parts = [part for part in urlparse(url).path.split("/") if part]
        if len(path_parts) >= 2 and path_parts[0] in {"reel", "reels", "p", "tv"}:
            return path_parts[1]
        return None

    @staticmethod
    def _extract_story_parts(url: str) -> tuple[str | None, str | None]:
        path_parts = [part for part in urlparse(url).path.split("/") if part]
        # stories/{username}/{story_id}
        if len(path_parts) >= 2 and path_parts[0] == "stories" and path_parts[1] != "highlights":
            username = path_parts[1]
            story_id = path_parts[2] if len(path_parts) >= 3 else None
            return username, story_id
        return None, None

    @staticmethod
    def _extract_dimensions(node: dict) -> tuple[int | None, int | None]:
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

    def _build_post_media(self, post: instaloader.Post) -> list[MediaItem]:
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
                media_url = post.video_url if is_video else post.url
                duration_raw = post.video_duration

            if not media_url:
                continue

            width, height = self._extract_dimensions(node)

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

    def _build_metadata_from_post(self, post: instaloader.Post, shortcode: str) -> InfoDict:
        view_count = None
        filesize_approx = None
        if post.is_video:
            view_count = post.video_view_count or post.video_play_count
            if post.video_url:
                filesize_approx = self._content_length(post.video_url)

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

    async def fetch_metadata(self, url: str) -> InfoDict | None:
        if url in self._metadata_cache:
            return self._metadata_cache[url]

        if "/stories/" in url:
            username, _ = self._extract_story_parts(url)
            if not username:
                return None
            info = {
                "author_username": username,
                "posted_at": None,
                "duration": 0,
                "view_count": None,
                "comment_count": None,
                "like_count": None,
                "description": "",
            }
            self._metadata_cache[url] = info
            return info

        shortcode = self._extract_shortcode(url)
        if not shortcode:
            return None

        def _fetch():
            try:
                post = instaloader.Post.from_shortcode(self.loader.context, shortcode)
                return self._build_metadata_from_post(post, shortcode)
            except Exception as exc:
                print("Metadata fetch failed:", exc)
                return None

        info = await asyncio.to_thread(_fetch)
        if info:
            self._metadata_cache[url] = info
        return info

    async def download_media(self, url: str, format_id: str | None = None) -> DownloadResult:
        metadata = await self.fetch_metadata(url)
        if not metadata:
            return DownloadResult(media_items=[], info=None)

        def _resolve():
            try:
                if "/stories/" in url:
                    return self._download_story_url(url)
                return self._download_post_url(url)
            except Exception as exc:
                print("Download failed:", exc)
                return DownloadResult(media_items=[], info=None)

        return await asyncio.to_thread(_resolve)

    def _download_post_url(self, url: str) -> DownloadResult:
        shortcode = self._extract_shortcode(url)
        if not shortcode:
            return DownloadResult(media_items=[], info=None)

        post = instaloader.Post.from_shortcode(self.loader.context, shortcode)
        try:
            media_items = self._build_post_media(post)
        except Exception:
            media_items = []

        info = self._metadata_cache.get(url) or self._build_metadata_from_post(post, shortcode)
        return DownloadResult(media_items=media_items, info=info)

    def _download_story_url(self, url: str) -> DownloadResult:
        username, story_id = self._extract_story_parts(url)
        if not username:
            return DownloadResult(media_items=[], info=None)

        profile = instaloader.Profile.from_username(self.loader.context, username)
        media_items: list[MediaItem] = []

        for story in self.loader.get_stories(userids=[profile.userid]):
            for item in story.get_items():
                if story_id and str(item.mediaid) != story_id:
                    continue

                is_video = item.is_video
                media_url = item.video_url if is_video else item.url
                
                width, height = self._extract_dimensions(getattr(item, "_node", {}))
                media_items.append(
                    MediaItem(
                        kind="video" if is_video else "photo",
                        url=media_url,
                        thumbnail_url=item.url,
                        width=width,
                        height=height,
                        title=f"{username} Story",
                        author=username
                    )
                )

            if story_id and media_items:
                break

        if story_id and media_items:
            media_items = media_items[:1]

        info: InfoDict = {
            "author_username": username,
            "posted_at": None,
            "duration": 0,
            "view_count": None,
            "comment_count": None,
            "like_count": None,
            "description": "",
        }
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
