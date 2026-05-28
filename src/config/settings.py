import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
MAX_VIDEO_SIZE_BYTES = 50 * 1024 * 1024
TELEGRAM_MEDIA_GROUP_LIMIT = 10
TELEGRAM_UPLOAD_TIMEOUT_SECONDS = 900
USER_COOLDOWN_SECONDS = 5
DEFAULT_CAPTION = "⚡️ @olibber_bot orqali yuklab olindi"
GROUP_NEED_ADMIN_MESSAGE = (
	"Assalomu alaykum. Meni admin qiling, shunda men Instagram havolalaridan videolarni yuboraman."
)

# Optional Instagram session-based auth for authenticated metadata fetching
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")
INSTALOADER_SESSION_B64 = os.getenv("INSTALOADER_SESSION_B64")

INSTAGRAM_TEMPORARILY_UNAVAILABLE_MESSAGE = (
	"Instagram hozircha vaqtincha ishlamayapti. Iltimos, keyinroq yana urinib ko'ring."
)
