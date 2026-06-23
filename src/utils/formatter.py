from datetime import datetime, timezone
from html import escape
from typing import Optional

from src.core.platforms.base import AbstractVideoFormatter, InfoDict

MONTH_NAMES_UZ = {
    1: "Yanvar",
    2: "Fevral",
    3: "Mart",
    4: "Aprel",
    5: "May",
    6: "Iyun",
    7: "Iyul",
    8: "Avgust",
    9: "Sentyabr",
    10: "Oktabr",
    11: "Noyabr",
    12: "Dekabr",
}


def humanize_number(num: int | float | str | None) -> str:
    if num is None or num == "":
        return "0"
    try:
        n = float(num)
        if n >= 1_000_000_000:
            return f"{n / 1_000_000_000:.1f} mlrd"
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f} mln"
        if n >= 1_000:
            return f"{n / 1_000:.1f} ming"
        return str(int(n))
    except (ValueError, TypeError):
        return str(num)


def humanize_duration(seconds: int | float | str | None) -> str:
    if seconds is None or seconds == "":
        return "Noma'lum"
    try:
        s = int(float(seconds))
        if s <= 0:
            return "Noma'lum"
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"
    except (ValueError, TypeError):
        return "Noma'lum"


def _parse_datetime(value: datetime | str | int | None) -> datetime | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)

    if isinstance(value, str):
        if value.isdigit() and len(value) == 8:
            return datetime.strptime(value, "%Y%m%d").replace(tzinfo=timezone.utc)

        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    return None


def format_posted(dt: datetime | str | int | None) -> str | None:
    parsed = _parse_datetime(dt)
    if not parsed:
        return None

    now = datetime.now(timezone.utc)
    delta_seconds = max(0, int((now - parsed).total_seconds()))

    year_seconds = 365 * 24 * 3600
    month_seconds = 30 * 24 * 3600
    day_seconds = 24 * 3600
    hour_seconds = 3600

    years, remaining = divmod(delta_seconds, year_seconds)
    months, remaining = divmod(remaining, month_seconds)
    days, remaining = divmod(remaining, day_seconds)
    hours, _ = divmod(remaining, hour_seconds)

    if years:
        age = f"{years} yil {months} oy oldin" if months else f"{years} yil oldin"
    elif months:
        age = f"{months} oy {days} kun oldin" if days else f"{months} oy oldin"
    elif days:
        age = f"{days} kun oldin"
    elif hours:
        age = f"{hours} soat oldin"
    else:
        age = "hozirgina"

    return f"{MONTH_NAMES_UZ[parsed.month]} {parsed.day}, {parsed.year} ({age})"


def safe_text(text: str | None) -> str:
    if not text:
        return ""
    return escape(text)


TELEGRAM_MESSAGE_LIMIT = 4096


class AbstractBaseFormatter(AbstractVideoFormatter):
    def _get_description_lines(self, description: str | None, base_lines: list[str]) -> list[str]:
        if not description:
            return []
        desc_text = safe_text(description)
        candidate = ["📝 <b>Tavsif:</b>", f"<blockquote expandable>{desc_text}</blockquote>"]
        if len("\n".join(base_lines + candidate)) <= TELEGRAM_MESSAGE_LIMIT:
            return candidate
        return ["📝 Tavsif: Juda uzun bo'lgani sabablik yubora olmayman."]

    def _build_common_metrics(self, info: InfoDict) -> list[str]:
        lines: list[str] = []

        posted = format_posted(info.get("posted_at"))
        if posted:
            lines.append(f"📅 <b>Joylangan:</b> {posted}")

        duration_value = info.get("duration")
        if duration_value:
            lines.append(f"⏱️ <b>Davomiyligi:</b> {humanize_duration(duration_value)}")

        view_count = info.get("view_count")
        if view_count is not None:
            lines.append(f"👀 <b>Ko'rishlar:</b> {humanize_number(view_count)}")

        like_count = info.get("like_count")
        if like_count is not None:
            lines.append(f"❤️ <b>Yoqtirishlar:</b> {humanize_number(like_count)}")

        comment_count = info.get("comment_count")
        if comment_count is not None:
            lines.append(f"💬 <b>Izohlar:</b> {humanize_number(comment_count)}")

        return lines

    def build_summary(self, info: InfoDict) -> str:
        pass



