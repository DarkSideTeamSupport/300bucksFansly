from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.access import is_allowed_chat


class AdminAccessMiddleware(BaseMiddleware):
	async def __call__(
		self,
		handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
		event: TelegramObject,
		data: dict[str, Any],
	) -> Any:
		chat_id = _chat_id(event)
		if not await is_allowed_chat(chat_id):
			if isinstance(event, Message):
				await event.answer(
					"Нет доступа.\nДобавьте ваш chat_id в ADMIN_CHAT_IDS (.env)."
				)
			elif isinstance(event, CallbackQuery):
				await event.answer("Нет доступа", show_alert=True)
			return None
		return await handler(event, data)


def _chat_id(event: TelegramObject) -> int | None:
	if isinstance(event, Message):
		return event.chat.id if event.chat else None
	if isinstance(event, CallbackQuery):
		if event.message and event.message.chat:
			return event.message.chat.id
		if event.from_user:
			return event.from_user.id
	return None
