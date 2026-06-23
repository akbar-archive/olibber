"""File system helpers: finding downloaded files, streaming, content-length probing."""

import os
import tempfile
from pathlib import Path
from typing import AsyncIterable
from urllib.request import Request, urlopen

import instaloader


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
    async def stream_file(
        file_path: str, cleanup: tempfile.TemporaryDirectory[str]
    ) -> AsyncIterable[bytes]:
        try:
            with open(file_path, "rb") as file_handle:
                while True:
                    chunk = file_handle.read(65536)
                    if not chunk:
                        break
                    yield chunk
        finally:
            cleanup.cleanup()

    def download_post_to_temp_file(
        self, loader: instaloader.Instaloader, post: instaloader.Post
    ) -> tuple[str | None, tempfile.TemporaryDirectory[str]]:
        temp_dir = tempfile.TemporaryDirectory()
        try:
            loader.download_post(post, target=temp_dir.name)
        except Exception:
            temp_dir.cleanup()
            raise
        return self._find_downloaded_video_file(temp_dir.name), temp_dir
