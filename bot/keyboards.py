from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from web.services.migration.settings import MigrationSettings


PROFILE_FIELDS = (
	("target_username", "Username"),
	("bio", "Bio"),
	("target_account", "Целевой аккаунт"),
)

NETWORK_FIELDS = (
	("notify_group_link", "Ссылка на группу"),
	("notify_message", "Сообщение в группе"),
	("default_proxy", "Прокси"),
	("concurrency", "Параллельность"),
)

BOOL_FIELDS = (
	("open_privacy", "Приватность"),
	("change_profile", "Профиль"),
	("notify_group", "Уведомление"),
	("migrate_groups", "Перенос групп"),
	("export_media", "Медиа"),
)

TEXT_FIELDS = PROFILE_FIELDS + NETWORK_FIELDS


def root_keyboard() -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup(
		inline_keyboard=[
			[
				InlineKeyboardButton(text="Миграция", callback_data="menu:migration"),
				InlineKeyboardButton(text="Сайт", callback_data="menu:site"),
			],
			[InlineKeyboardButton(text="Обновить", callback_data="menu:root")],
		]
	)


def migration_keyboard(settings: MigrationSettings) -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup(
		inline_keyboard=[
			[
				InlineKeyboardButton(text="Профиль", callback_data="menu:profile"),
				InlineKeyboardButton(text="Шаги", callback_data="menu:steps"),
			],
			[
				InlineKeyboardButton(text="Сеть", callback_data="menu:network"),
				InlineKeyboardButton(text="Действия", callback_data="menu:actions"),
			],
			[InlineKeyboardButton(text="« Назад", callback_data="menu:root")],
		]
	)


def profile_keyboard(settings: MigrationSettings) -> InlineKeyboardMarkup:
	rows = _field_rows(PROFILE_FIELDS, settings)
	rows.append([InlineKeyboardButton(text="« Назад", callback_data="menu:migration")])
	return InlineKeyboardMarkup(inline_keyboard=rows)


def network_keyboard(settings: MigrationSettings) -> InlineKeyboardMarkup:
	rows = _field_rows(NETWORK_FIELDS, settings)
	chat_short = _short(settings.bot_chat_id or "-")
	rows.append(
		[InlineKeyboardButton(text=f"Логи chat_id: {chat_short}", callback_data="bind_chat")]
	)
	rows.append([InlineKeyboardButton(text="« Назад", callback_data="menu:migration")])
	return InlineKeyboardMarkup(inline_keyboard=rows)


def bind_chat_keyboard() -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup(
		inline_keyboard=[
			[InlineKeyboardButton(text="Этот чат", callback_data="bind_chat:here")],
			[InlineKeyboardButton(text="Указать / переслать из группы", callback_data="bind_chat:manual")],
			[InlineKeyboardButton(text="« Назад", callback_data="menu:network")],
		]
	)


def steps_keyboard(settings: MigrationSettings) -> InlineKeyboardMarkup:
	rows: list[list[InlineKeyboardButton]] = []
	row: list[InlineKeyboardButton] = []
	for key, title in BOOL_FIELDS:
		enabled = bool(getattr(settings, key))
		mark = "ON" if enabled else "OFF"
		row.append(
			InlineKeyboardButton(text=f"{title}: {mark}", callback_data=f"toggle:{key}")
		)
		if len(row) == 2:
			rows.append(row)
			row = []
	if row:
		rows.append(row)
	rows.append([InlineKeyboardButton(text="« Назад", callback_data="menu:migration")])
	return InlineKeyboardMarkup(inline_keyboard=rows)


def actions_keyboard() -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup(
		inline_keyboard=[
			[InlineKeyboardButton(text="Показать все настройки", callback_data="show")],
			[InlineKeyboardButton(text="session → tdata", callback_data="convert_tdata")],
			[InlineKeyboardButton(text="Сбросить шаги миграции", callback_data="reset_steps")],
			[InlineKeyboardButton(text="« Назад", callback_data="menu:migration")],
		]
	)


def cancel_keyboard(back_to: str = "menu:migration") -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup(
		inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data=back_to)]]
	)


def main_keyboard(settings: MigrationSettings) -> InlineKeyboardMarkup:
	"""Совместимость со старыми вызовами — корневое меню миграции."""
	return migration_keyboard(settings)


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
	text = str(value or "-")
	if len(text) > 22:
		return text[:19] + "..."
	return text
