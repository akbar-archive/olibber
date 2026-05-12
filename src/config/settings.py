import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
MAX_VIDEO_SIZE_BYTES = 50 * 1024 * 1024
TELEGRAM_MEDIA_GROUP_LIMIT = 10
TELEGRAM_UPLOAD_TIMEOUT_SECONDS = 900
USER_COOLDOWN_SECONDS = 5
DEFAULT_CAPTION = "⚡️ @olibber_bot orqali yuklab olindi"
