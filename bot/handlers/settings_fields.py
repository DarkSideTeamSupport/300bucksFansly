from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.handlers.settings_ui import FIELD_BACK, FIELD_TITLES, format_settings, steps_menu_text
from bot.keyboards import account_keyboard, cancel_keyboard, steps_keyboard
from bot.states import SettingsStates
from web.services.migration.settings import settings_repo

router = Router()


@router.callback_query(F.data.startswith("toggle:"))
async def cb_toggle(callback: CallbackQuery) -> None:
	key = callback.data.split(":", 1)[1]
	settings = await settings_repo.load()
	if not hasattr(settings, key):
		await callback.answer("Неизвестный параметр", show_alert=True)
		return
	current = bool(getattr(settings, key))
	setattr(settings, key, not current)
	await settings_repo.save(settings)
	try:
		await callback.message.edit_text(
			steps_menu_text(),
			reply_markup=steps_keyboard(settings),
			parse_mode="HTML",
		)
	except TelegramBadRequest as error:
		if "message is not modified" not in str(error):
			raise
	await callback.answer(
		f"{FIELD_TITLES.get(key, key)}: {'ON' if not current else 'OFF'}"
	)


@router.callback_query(F.data.startswith("set:"))
async def cb_set(callback: CallbackQuery, state: FSMContext) -> None:
	key = callback.data.split(":", 1)[1]
	title = FIELD_TITLES.get(key, key)
	back = FIELD_BACK.get(key, "menu:account")
	await state.set_state(SettingsStates.waiting_value)
	await state.update_data(field=key, back=back)
	await callback.message.edit_text(
		f"Введите новое значение для <b>{title}</b>\n"
		f"Отправьте <code>-</code> чтобы очистить.",
		reply_markup=cancel_keyboard(back),
		parse_mode="HTML",
	)
	await callback.answer()


@router.message(SettingsStates.waiting_value)
async def on_value(message: Message, state: FSMContext) -> None:
	data = await state.get_data()
	key = data.get("field")
	if not key:
		await state.clear()
		await message.answer("Сессия сброшена. /menu")
		return

	raw = (message.text or "").strip()
	settings = await settings_repo.load()

	value = "" if raw == "-" else raw
	setattr(settings, key, value)

	await settings_repo.save(settings)
	await state.clear()
	await message.answer(
		await format_settings(),
		reply_markup=account_keyboard(settings),
		parse_mode="HTML",
	)
