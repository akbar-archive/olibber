from aiogram import types
from src.core.engine.registry import resolve_platform
from src.core.engine.manager import VideoManager
import uuid

async def handle_inline(inline_query: types.InlineQuery):
    url = inline_query.query.strip()
    if not url:
        return

    platform = resolve_platform(url)
    if not platform:
        return

    manager = VideoManager(url, platform)
    try:
        metadata = await manager.fetch_metadata()
        if not metadata:
            return

        # For Inline mode, we can't easily do "Quality selection" before sending,
        # but we can provide two options: Video and Audio.
        
        results = []
        
        # Option 1: Video
        results.append(
            types.InlineQueryResultVideo(
                id=str(uuid.uuid4()),
                video_url=url,  # This is tricky since it's a page URL, not direct
                mime_type="video/mp4",
                thumbnail_url=metadata.get("thumbnail", ""),
                title=f"🎬 Video yuborish: {metadata.get('title', "Noma'lum")}",
                description=url,
                caption=metadata.get("title", ""),
                # To make this work properly with our streaming, we'd need a 
                # permanent direct URL or use InputTextMessageContent to trigger the bot
            )
        )
        
        # Actually, for most bots, Inline mode sends a button that the user clicks,
        # OR it uses a specific "Proxy URL" if we had one.
        # Given the zero-disk architecture, the best way for Inline is often 
        # to send a message that triggers the bot's own processing.
        
        # However, Telegram's InlineQueryResultVideo REQUIRES a direct video URL.
        # Since we don't always have one, we'll send an article
        # that, when clicked, sends the link to the chat, triggering the bot.
        
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
    except Exception:
        pass
