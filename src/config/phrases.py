import random

LOADING_PHRASES = [
    "Siz uchun bir narsa tayyorlayapman...",
    "Kutib turing, men ishlayapman...",
    "Siz uchun biroz sehr tayyorlayapman...",
    "Kontentingizni darhol olib kelaman...",
    "So'rovingizni mehr bilan qayta ishlayapman...",
    "Deyarli tayyor, bir lahza...",
    "Hammasini siz uchun tayyorlayapman...",
]

def get_random_phrase() -> str:
    return random.choice(LOADING_PHRASES)
