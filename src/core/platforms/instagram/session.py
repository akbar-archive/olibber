"""Instagram session management: loads credentials from env vars into instaloader."""

import base64
import os
import tempfile
from urllib.parse import unquote

import instaloader

from src.config.settings import (
    INSTAGRAM_USERNAME,
    INSTALOADER_SESSION_B64,
    INSTAGRAM_SESSIONID,
)


class InstagramSessionManager:
    def __init__(self) -> None:
        self.loader = instaloader.Instaloader(
            quiet=True,
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            save_metadata=False,
            compress_json=False,
            request_timeout=60.0,
        )
        self.session_loaded = False
        self.last_error: str | None = None
        if INSTALOADER_SESSION_B64 and INSTAGRAM_USERNAME:
            self.load_session_from_env()
        elif INSTAGRAM_SESSIONID:
            self.load_session_from_cookie(INSTAGRAM_SESSIONID)

    def load_session_from_env(self) -> None:
        import logging
        logger = logging.getLogger(__name__)
        try:
            decoded = base64.b64decode(INSTALOADER_SESSION_B64)
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".session")
            try:
                temp_file.write(decoded)
                temp_file.flush()
                temp_file.close()
                self.loader.load_session_from_file(INSTAGRAM_USERNAME, filename=temp_file.name)
                self.session_loaded = True
                self.last_error = None
            finally:
                try:
                    os.unlink(temp_file.name)
                except Exception:
                    pass
        except Exception as exc:
            self.last_error = f"Instagram sessiyasini yuklab bo'lmadi: {exc}"
            logger.error("Failed to load Instagram session: %s", exc)

    def load_session_from_cookie(self, session_id: str) -> None:
        import logging
        logger = logging.getLogger(__name__)
        try:
            session_id = unquote(session_id)
            self.loader.context._session.cookies.set(
                "sessionid", session_id, domain=".instagram.com"
            )
            self.session_loaded = True
            self.last_error = None
            logger.info("Instagram session loaded from INSTAGRAM_SESSIONID cookie.")
        except Exception as exc:
            self.last_error = f"INSTAGRAM_SESSIONID dan sessiya yuklab bo'lmadi: {exc}"
            logger.error("Failed to load session from cookie: %s", exc)

    def require_session(self) -> bool:
        if self.session_loaded:
            return True
        self.last_error = (
            "Instagram sessiyasi sozlanmagan. "
            "INSTAGRAM_SESSIONID yoki INSTALOADER_SESSION_B64 ni belgilang."
        )
        import logging
        logging.getLogger(__name__).warning(self.last_error)
        return False
