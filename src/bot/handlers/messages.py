import logging
import re

from aiogram import Bot, F, Router, types

from src.constants.messages import GROUP_NEED_ADMIN_MESSAGE
from src.core.engine.job_controller import job_controller
from src.core.engine.registry import resolve_platform
from src.services.media_processor import MediaProcessorService

logger = logging.getLogger(__name__)
router = Router()

_URL_PATTERN = re.compile(r"^https?://\S+$", re.IGNORECASE)


async def _is_bot_admin(bot: Bot, chat_id: int) -> bool:
    chat_member = await bot.get_chat_member(chat_id, bot.id)
    return chat_member.status in {"administrator", "creator"}


async def _prepare_and_validate_url(message: types.Message) -> tuple[str | None, bool]:
    text = (message.text or "").strip()
    if not text or not _URL_PATTERN.fullmatch(text):
        return None, False

    is_group_chat = message.chat.type in {"group", "supergroup"}
    return text, is_group_chat


async def _handle_lock_and_cooldown(
    user_id: int, message: types.Message, track_user_job: bool
) -> bool:
    if not track_user_job:
        return True

    can_proceed, remaining = await job_controller.acquire(user_id)
    if not can_proceed:
        if remaining > 0:
            await message.answer(
                f"Siz {remaining} soniyadan so'ng yana yuborishingiz mumkin"
            )
        else:
            await message.answer("Men hozir sizning so'rovingiz bilan bandman")
        return False

    return True


@router.message(F.text.regexp(r"https?://"))
async def handle_link(message: types.Message, bot: Bot):
    url, is_group_chat = await _prepare_and_validate_url(message)
    if not url:
        return

    platform = resolve_platform(url)
    if not platform:
        if not is_group_chat:
            await message.answer(
                "Bu havola qo'llab-quvvatlanmaydi. Faqat Instagram va YouTube havolalari ishlaydi.",
                reply_to_message_id=message.message_id,
            )
        return

    link_checker = platform.create_link_checker()
    if not link_checker.is_valid(url):
        return

    if is_group_chat and not await _is_bot_admin(bot, message.chat.id):
        await message.answer(
            GROUP_NEED_ADMIN_MESSAGE,
            reply_to_message_id=message.message_id,
        )
        return

    user_id = message.from_user.id if message.from_user else 0
    track_user_job = not is_group_chat

    if not await _handle_lock_and_cooldown(user_id, message, track_user_job):
        return

    if track_user_job:
        await job_controller.set_pending_url(user_id, url)

    service = MediaProcessorService(bot)
    await service.process_request(
        message=message,
        url=url,
        platform=platform,
        is_group_chat=is_group_chat,
        track_user_job=track_user_job,
    )
