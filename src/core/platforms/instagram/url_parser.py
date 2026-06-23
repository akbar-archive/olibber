"""URL parsing helpers for Instagram links."""

from urllib.parse import urlparse


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
