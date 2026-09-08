from __future__ import annotations

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery

from bot.keyboards import BOOL_FIELDS, TEXT_FIELDS
from web.services.migration.settings import settings_repo

FIELD_TITLES = {key: title for key, title in TEXT_FIELDS + BOOL_FIELDS}
FIELD_BACK = {
	**{key: "menu:profile" for key, _ in (
		("target_username", ""),
		("bio", ""),
		("target_account", ""),
	)},
	**{key: "menu:network" for key, _ in (
		("notify_group_link", ""),
		("notify_message", ""),
		("default_proxy", ""),
		("concurrency", ""),
	)},
}


async def format_settings() -> str:
	s = await settings_repo.load()
	lines = [
		"<b>Миграция</b>",
		"",
		f"Username: <code>{s.target_username or '-'}</code>",
		f"Bio: <code>{s.bio or '-'}</code>",
		f"Целевой аккаунт: <code>{s.target_account or '-'}</code>",
		f"Группа: <code>{s.notify_group_link or '-'}</code>",
		f"Сообщение: <code>{s.notify_message or '-'}</code>",
		f"Прокси: <code>{s.default_proxy or '-'}</code>",
		f"Параллельность: <code>{s.concurrency}</code>",
		f"Chat ID логов: <code>{s.bot_chat_id or '-'}</code>",
		"",
		f"Приватность: {'ON' if s.open_privacy else 'OFF'}",
		f"Профиль: {'ON' if s.change_profile else 'OFF'}",
		f"Уведомление: {'ON' if s.notify_group else 'OFF'}",
		f"Перенос групп: {'ON' if s.migrate_groups else 'OFF'}",
		f"Медиа: {'ON' if s.export_media else 'OFF'}",
	]
	return "\n".join(lines)


async def root_text() -> str:
	s = await settings_repo.load()
	return (
		"<b>TGDumper</b>\n"
		"Выберите раздел.\n\n"
		f"Логи → chat_id: <code>{s.bot_chat_id or '-'}</code>"
	)


async def network_text(extra: str = "") -> str:
	s = await settings_repo.load()
	text = (
		"<b>Сеть и отчёты</b>\n"
		"Группа-маяк, прокси, параллельность, chat_id логов.\n"
		f"Логи chat_id: <code>{s.bot_chat_id or '-'}</code>"
	)
	if extra:
		text += f"\n{extra}"
	return text


async def edit_menu(callback: CallbackQuery, text: str, markup) -> None:
	try:
		await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
	except TelegramBadRequest as error:
		if "message is not modified" not in str(error):
			raise
	await callback.answer()
