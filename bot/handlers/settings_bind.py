import asyncio

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.chat_id import resolve_chat_id
from bot.config import BOT_TOKEN
from bot.handlers.settings_ui import edit_menu, network_text
from bot.keyboards import bind_chat_keyboard, cancel_keyboard, network_keyboard
from bot.states import SettingsStates
from web.services.migration.settings import settings_repo

router = Router()


@router.callback_query(F.data == "bind_chat")
async def cb_bind_menu(callback: CallbackQuery, state: FSMContext) -> None:
	await state.clear()
	s = await settings_repo.load()
	await edit_menu(
		callback,
		"<b>Chat ID для логов</b>\n"
		f"Сейчас: <code>{s.bot_chat_id or '-'}</code>\n\n"
		"1) Добавьте бота в группу\n"
		"2) Привяжите «Этот чат» <b>из группы</b> или укажите id / "
		"перешлите любое сообщение из группы\n"
		"Супергруппы обычно выглядят как <code>-100…</code>",
		bind_chat_keyboard(),
	)


@router.callback_query(F.data == "bind_chat:here")
async def cb_bind_here(callback: CallbackQuery, state: FSMContext) -> None:
	await state.clear()
	settings = await settings_repo.load()
	token = (settings.bot_token or BOT_TOKEN or "").strip()
	chat_id = str(callback.message.chat.id)
	resolved, detail = await asyncio.to_thread(resolve_chat_id, token, chat_id)
	if not resolved:
		await callback.answer(detail[:180], show_alert=True)
		return
	settings.bot_chat_id = resolved
	await settings_repo.save(settings)
	await callback.answer(f"Привязан: {resolved}", show_alert=True)
	await edit_menu(
		callback,
		await network_text(f"Сохранено: <code>{resolved}</code> ({detail})."),
		network_keyboard(settings),
	)


@router.callback_query(F.data == "bind_chat:manual")
async def cb_bind_manual(callback: CallbackQuery, state: FSMContext) -> None:
	await state.set_state(SettingsStates.waiting_log_chat_id)
	await callback.message.edit_text(
		"Отправьте <b>chat_id</b> группы/канала "
		"(пример <code>-1001234567890</code>)\n"
		"или <b>перешлите</b> любое сообщение из этой группы боту.\n"
		"Бот должен уже быть участником группы.\n"
		"Отправьте <code>-</code> чтобы очистить.",
		reply_markup=cancel_keyboard("menu:network"),
		parse_mode="HTML",
	)
	await callback.answer()


@router.message(SettingsStates.waiting_log_chat_id)
async def on_log_chat_id(message: Message, state: FSMContext) -> None:
	settings = await settings_repo.load()
	token = (settings.bot_token or BOT_TOKEN or "").strip()

	if message.forward_from_chat is not None:
		raw = str(message.forward_from_chat.id)
	elif message.forward_origin is not None and getattr(
		message.forward_origin, "chat", None
	) is not None:
		raw = str(message.forward_origin.chat.id)
	else:
		raw = (message.text or "").strip()

	if raw == "-":
		settings.bot_chat_id = ""
		await settings_repo.save(settings)
		await state.clear()
		await message.answer(
			await network_text("Chat ID логов очищен."),
			reply_markup=network_keyboard(settings),
			parse_mode="HTML",
		)
		return

	resolved, detail = await asyncio.to_thread(resolve_chat_id, token, raw)
	if not resolved:
		await message.answer(f"Не удалось привязать:\n{detail}")
		return

	settings.bot_chat_id = resolved
	await settings_repo.save(settings)
	await state.clear()
	await message.answer(
		await network_text(f"Сохранено: <code>{resolved}</code>\n{detail}"),
		reply_markup=network_keyboard(settings),
		parse_mode="HTML",
	)
