from src.core.platforms.instagram import InstagramPlatform
from src.core.platforms.youtube import YoutubePlatform
from src.core.platforms.base import AbstractPlatform

_platforms: list[AbstractPlatform] = [
    InstagramPlatform(),
    YoutubePlatform(),
]

def resolve_platform(url: str) -> AbstractPlatform | None:
    for platform in _platforms:
        if platform.supports(url):
            return platform
    return None
