"""Runtime configuration loaded from environment variables."""

import os

from dotenv import load_dotenv

load_dotenv()

# Telegram
TOKEN: str | None = os.getenv("TELEGRAM_BOT_TOKEN")

# Instagram auth
INSTAGRAM_USERNAME: str | None = os.getenv("INSTAGRAM_USERNAME")
INSTALOADER_SESSION_B64: str | None = os.getenv("INSTALOADER_SESSION_B64")
INSTAGRAM_SESSIONID: str = os.getenv("INSTAGRAM_SESSIONID", "")
