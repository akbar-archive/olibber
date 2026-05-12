from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup
from src.core.platforms.base import MediaItem

def build_format_keyboard(media_item: MediaItem, url: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    # Sort formats by resolution if possible
    formats = sorted(media_item.formats, key=lambda x: (x.is_video, x.resolution or ""), reverse=True)
    
    # Add Video Formats
    for fmt in formats:
        if not fmt.is_video:
            continue
        
        label = f"🎬 {fmt.resolution or fmt.format_id} ({fmt.extension})"
        # data format: download:<platform>:<format_id>:<url_base64_or_id>
        # To keep callback data small, we might need a better way. 
        # For now, let's use a simple approach.
        builder.button(text=label, callback_data=f"dl:v:{fmt.format_id}")

    # Add Audio Formats (best one)
    best_audio = next((f for f in formats if not f.is_video), None)
    if best_audio:
        builder.button(text="🎵 Audio (MP3)", callback_data=f"dl:a:{best_audio.format_id}")
    
    builder.adjust(1)
    return builder.as_markup()
