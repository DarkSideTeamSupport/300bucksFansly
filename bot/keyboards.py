from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from web.services.migration.settings import MigrationSettings


# Управление аккаунтом — каждый пункт отдельной кнопкой
ACCOUNT_TEXT_FIELDS = (
	("target_username", "Username"),
	("bio", "Bio"),
	("target_account", "Целевой аккаунт"),
	("notify_group_link", "Ссылка на группу"),
	("notify_message", "Сообщение в группе"),
	("default_proxy", "Прокси"),
)

BOOL_FIELDS = (
	("notify_group", "Сообщение в группу"),
	("open_privacy", "Приватность"),
	("change_profile", "Профиль"),
	("export_media", "Дампер фото/видео"),
	("migrate_groups", "Перенос групп"),
)

# совместимость со старыми импортами
PROFILE_FIELDS = (
	("target_username", "Username"),
	("bio", "Bio"),
	("target_account", "Целевой аккаунт"),
)
NETWORK_FIELDS = (
	("notify_group_link", "Ссылка на группу"),
	("notify_message", "Сообщение в группе"),
	("default_proxy", "Прокси"),
)
TEXT_FIELDS = ACCOUNT_TEXT_FIELDS


def root_keyboard() -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup(
		inline_keyboard=[
			[InlineKeyboardButton(text="🌐 Сайт", callback_data="menu:site")],
			[
				InlineKeyboardButton(
					text="👤 Управление аккаунтом", callback_data="menu:account"
				)
			],
			[InlineKeyboardButton(text="🔄 Обновить", callback_data="menu:root")],
		]
	)


def account_keyboard(settings: MigrationSettings) -> InlineKeyboardMarkup:
	from web.services.migration.target_joiner_ipc import ipc_store

	rows = _field_rows(ACCOUNT_TEXT_FIELDS, settings)
	chat_short = _short(settings.bot_chat_id or "-")
	joiner_short = _short(ipc_store.status_label())
	rows.append(
		[
			InlineKeyboardButton(
				text=f"Chat ID логов: {chat_short}", callback_data="bind_chat"
			)
		]
	)
	rows.append(
		[
			InlineKeyboardButton(
				text=f"🔗 Инвайт-аккаунт: {joiner_short}",
				callback_data="target_joiner:menu",
			)
		]
	)
	rows.append([InlineKeyboardButton(text="⚙️ Что делать после входа", callback_data="menu:steps")])
	rows.append([InlineKeyboardButton(text="🛠 Служебное", callback_data="menu:actions")])
	rows.append([InlineKeyboardButton(text="« Назад", callback_data="menu:root")])
	return InlineKeyboardMarkup(inline_keyboard=rows)


def migration_keyboard(settings: MigrationSettings) -> InlineKeyboardMarkup:
	"""Алиас: старое меню миграции = управление аккаунтом."""
	return account_keyboard(settings)


def profile_keyboard(settings: MigrationSettings) -> InlineKeyboardMarkup:
	return account_keyboard(settings)


def network_keyboard(settings: MigrationSettings) -> InlineKeyboardMarkup:
	return account_keyboard(settings)


def bind_chat_keyboard() -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup(
		inline_keyboard=[
			[InlineKeyboardButton(text="Этот чат", callback_data="bind_chat:here")],
			[
				InlineKeyboardButton(
					text="Указать / переслать из группы", callback_data="bind_chat:manual"
				)
			],
			[InlineKeyboardButton(text="« Назад", callback_data="menu:account")],
		]
	)


def steps_keyboard(settings: MigrationSettings) -> InlineKeyboardMarkup:
	rows: list[list[InlineKeyboardButton]] = []
	for key, title in BOOL_FIELDS:
		enabled = bool(getattr(settings, key))
		mark = "✅" if enabled else "⬜️"
		rows.append(
			[
				InlineKeyboardButton(
					text=f"{mark} {title}", callback_data=f"toggle:{key}"
				)
			]
		)
	rows.append([InlineKeyboardButton(text="« Назад", callback_data="menu:account")])
	return InlineKeyboardMarkup(inline_keyboard=rows)


def actions_keyboard() -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup(
		inline_keyboard=[
			[InlineKeyboardButton(text="📋 Показать текущие настройки", callback_data="show")],
			[
				InlineKeyboardButton(
					text="📦 Собрать tdata из .session", callback_data="convert_tdata"
				)
			],
			[
				InlineKeyboardButton(
					text="♻️ Заново: сообщение + перенос групп", callback_data="reset_steps"
				)
			],
			[InlineKeyboardButton(text="« Назад", callback_data="menu:account")],
		]
	)


def cancel_keyboard(back_to: str = "menu:account") -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup(
		inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data=back_to)]]
	)


def main_keyboard(settings: MigrationSettings) -> InlineKeyboardMarkup:
	return account_keyboard(settings)


def _field_rows(
	fields: tuple[tuple[str, str], ...], settings: MigrationSettings
) -> list[list[InlineKeyboardButton]]:
	rows: list[list[InlineKeyboardButton]] = []
	for key, title in fields:
		value = getattr(settings, key)
		short = _short(value)
		rows.append(
			[InlineKeyboardButton(text=f"{title}: {short}", callback_data=f"set:{key}")]
		)
	return rows


def _short(value) -> str:
	text = str(value or "—")
	if len(text) > 24:
		return text[:21] + "..."
	return text
