"""Static user-facing message strings and loading phrases."""

import random

DEFAULT_CAPTION = "⚡️ @olibber_bot orqali yuklab olindi"

GROUP_NEED_ADMIN_MESSAGE = (
    "Assalomu alaykum. Meni admin qiling, shunda men Instagram havolalaridan videolarni yuboraman."
)

INSTAGRAM_TEMPORARILY_UNAVAILABLE_MESSAGE = (
    "Xozirda mendan ko'p inson foydalanmoqda. Iltimos, keyinroq yana urinib ko'ring."
)

LOADING_PHRASES = [
    "Siz uchun bir narsa tayyorlayapman...",
    "Kutib turing, men ishlayapman...",
    "Siz uchun biroz sehr tayyorlayapman...",
    "Kontentingizni darhol olib kelaman...",
    "So'rovingizni mehr bilan qayta ishlayapman...",
    "Deyarli tayyor, bir lahza...",
    "Hammasini siz uchun tayyorlayapman...",
    "Kontentingiz yo'lda...",
    "Yuklab olish muvaffaqiyatli yakunlanish arafasida...",
]


def get_random_phrase() -> str:
    return random.choice(LOADING_PHRASES)
