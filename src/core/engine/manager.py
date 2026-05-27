from src.core.platforms.base import AbstractPlatform

class VideoManager:
    def __init__(self, url: str, platform: AbstractPlatform):
        self.url = url
        self.platform = platform
        self.link_checker = platform.create_link_checker()
        self.downloader = platform.create_downloader()
        self.formatter = platform.create_formatter()
        self.info = None

    def is_valid_url(self) -> bool:
        return self.link_checker.is_valid(self.url)

    async def fetch_metadata(self):
        self.info = await self.downloader.fetch_metadata(self.url)
        return self.info

    async def fetch_summary(self):
        self.info = await self.fetch_metadata()
        if not self.info:
            return None
        return self.formatter.build_summary(self.info)

    async def download_media(self, format_id: str | None = None, metadata=None):
        result = await self.downloader.download_media(self.url, format_id, metadata=metadata or self.info)
        return result.media_items

    async def process(self, format_id: str | None = None):
        summary = await self.fetch_summary()
        media_items = await self.download_media(format_id)
        return summary, media_items

    def cleanup(self):
        return
