"""URL validation for Instagram links."""

import re

from src.core.platforms.base import AbstractLinkChecker


class InstagramLinkChecker(AbstractLinkChecker):
    _pattern = re.compile(
        r"^(https?://)?(www\.)?instagram\.com/(reel|reels|p|tv|stories)/.+$"
    )

    def is_valid(self, url: str) -> bool:
        if not url or " " in url:
            return False
        return bool(self._pattern.match(url))
