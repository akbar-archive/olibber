"""InstagramPlatform: the factory that wires together all Instagram components."""

from src.core.platforms.base import AbstractLinkChecker, AbstractPlatform, AbstractVideoDownloader, AbstractVideoFormatter
from src.core.platforms.instagram.link_checker import InstagramLinkChecker
from src.core.platforms.instagram.downloader import InstagramDownloader


class InstagramPlatform(AbstractPlatform):
    name = "instagram"

    def supports(self, url: str) -> bool:
        return "instagram.com/" in url

    def create_link_checker(self) -> AbstractLinkChecker:
        return InstagramLinkChecker()

    def create_downloader(self) -> AbstractVideoDownloader:
        return InstagramDownloader()

    def create_formatter(self) -> AbstractVideoFormatter:
        from src.core.platforms.instagram.formatter import InstagramFormatter
        return InstagramFormatter()
