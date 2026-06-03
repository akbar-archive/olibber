from src.core.platforms.instagram import InstagramPlatform
from src.core.platforms.base import AbstractPlatform

_platforms: list[AbstractPlatform] = [
    InstagramPlatform(),
]

def resolve_platform(url: str) -> AbstractPlatform | None:
    for platform in _platforms:
        if platform.supports(url):
            return platform
    return None
