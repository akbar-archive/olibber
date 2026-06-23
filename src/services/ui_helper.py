"""Helper class to manage user feedback and status updates."""

from aiogram import types

from src.constants.messages import INSTAGRAM_TEMPORARILY_UNAVAILABLE_MESSAGE, get_random_phrase


class UIHelper:
    @staticmethod
    async def send_loading_message(message: types.Message) -> types.Message:
        return await message.answer(
            get_random_phrase(),
            reply_to_message_id=message.message_id,
        )

    @staticmethod
    async def update_status_error(
        status_msg: types.Message | None, message: types.Message, error_text: str
    ) -> None:
        if status_msg:
            await status_msg.edit_text(error_text)
        else:
            await message.answer(
                error_text,
                reply_to_message_id=message.message_id,
            )

    @staticmethod
    async def update_status_instagram_error(
        status_msg: types.Message | None,
        message: types.Message,
        detailed_error: str | None = None,
    ) -> None:
        text = INSTAGRAM_TEMPORARILY_UNAVAILABLE_MESSAGE
        if detailed_error:
            text = f"{text}\n\n{detailed_error}"
        await UIHelper.update_status_error(status_msg, message, text)
