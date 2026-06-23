from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterable


InfoDict = dict[str, Any]


@dataclass
class MediaFormat:
    format_id: str
    extension: str
    resolution: str | None = None
    filesize: int | None = None
    vcodec: str | None = None
    acodec: str | None = None
    is_video: bool = True


@dataclass
class MediaItem:
    kind: str
    url: str | None = None
    stream: AsyncIterable[bytes] | None = None
    thumbnail_url: str | None = None
    width: int | None = None
    height: int | None = None
    duration: int | None = None
    title: str | None = None
    author: str | None = None
    file_id: str | None = None
    formats: list[MediaFormat] = field(default_factory=list)


@dataclass
class DownloadResult:
    media_items: list[MediaItem]
    info: InfoDict | None


class AbstractLinkChecker(ABC):
    @abstractmethod
    def is_valid(self, url: str) -> bool:
        pass


class AbstractVideoDownloader(ABC):
    @abstractmethod
    async def fetch_metadata(self, url: str) -> InfoDict | None:
        pass

    @abstractmethod
    async def download_media(
        self,
        url: str,
        format_id: str | None = None,
        metadata: InfoDict | None = None,
    ) -> DownloadResult:
        pass


class AbstractVideoFormatter(ABC):
    @abstractmethod
    def build_summary(self, info: InfoDict) -> str:
        pass


class AbstractPlatform(ABC):
    name: str

    @abstractmethod
    def supports(self, url: str) -> bool:
        pass

    @abstractmethod
    def create_link_checker(self) -> AbstractLinkChecker:
        pass

    @abstractmethod
    def create_downloader(self) -> AbstractVideoDownloader:
        pass

    @abstractmethod
    def create_formatter(self) -> AbstractVideoFormatter:
        pass
