"""Instagram specific media formatting."""

from src.core.platforms.base import InfoDict
from src.utils.formatter import AbstractBaseFormatter, safe_text


class InstagramFormatter(AbstractBaseFormatter):
    def _build_base_lines(self, info: InfoDict) -> list[str]:
        lines: list[str] = []

        author_username = info.get("author_username")
        if author_username:
            lines.append(
                f"👤 <b>Muallif:</b> <a href=\"https://www.instagram.com/{author_username}\">@{author_username}</a>"
            )

        lines.extend(self._build_common_metrics(info))

        return lines

    def build_summary(self, info: InfoDict) -> str:
        lines = self._build_base_lines(info)

        lines.extend(self._get_description_lines(info.get("description"), lines))

        return "\n".join(lines)

    def build_caption(self, info: InfoDict) -> str:
        lines = self._build_base_lines(info)

        description = info.get("description")
        if description:
            description_text = safe_text(description)
            base_caption = "\n".join(lines)

            for description_limit in (240, 180, 120, 80, 40):
                description_preview = description_text
                if len(description_preview) > description_limit:
                    description_preview = f"{description_preview[:description_limit].rstrip()}..."

                caption_parts = [
                    *lines,
                    "📝 <b>Tavsif:</b>",
                    f"<blockquote expandable>{description_preview}</blockquote>",
                ]
                caption = "\n".join(caption_parts)
                if len(caption) <= 1024:
                    return caption

            return base_caption

        return "\n".join(lines)
