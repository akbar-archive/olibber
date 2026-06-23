"""Extracts structured media data from instaloader Post objects."""

import instaloader

from src.core.platforms.base import InfoDict, MediaItem


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
                    author=post.owner_username,
                )
            )

        return media_items

    def build_metadata_from_post(
        self, post: instaloader.Post, shortcode: str, content_length_func
    ) -> InfoDict:
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
            "thumbnail": post.url,
        }
