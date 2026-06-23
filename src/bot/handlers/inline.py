import logging
import uuid

from aiogram import Router, types

from src.core.engine.registry import resolve_platform

logger = logging.getLogger(__name__)
router = Router()


@router.inline_query()
async def handle_inline(inline_query: types.InlineQuery):
    url = inline_query.query.strip()
    if not url:
        return

    platform = resolve_platform(url)
    if not platform:
        return

    downloader = platform.create_downloader()
    try:
        metadata = await downloader.fetch_metadata(url)
        if not metadata:
            return
        
        results = [
            types.InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title=f"📥 Yuklab olish: {metadata.get('title', 'Video')}",
                description=f"Manba: {platform.name.capitalize()}",
                thumbnail_url=metadata.get("thumbnail", ""),
                input_message_content=types.InputTextMessageContent(
                    message_text=url
                )
            )
        ]

        await inline_query.answer(results, cache_time=300)
    except Exception as exc:
        logger.exception("Inline query error for url '%s': %s", url, exc)
