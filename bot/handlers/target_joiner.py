from __future__ import annotations

import asyncio
import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.keyboards import cancel_keyboard
from bot.states import TargetJoinerStates
from web.services.migration.settings import settings_repo
from web.services.migration.target_joiner_ipc import ipc_store

router = Router()

_PHONE_RE = re.compile(r"^\+?\d{8,15}$")


def _joiner_keyboard() -> InlineKeyboardMarkup:
	state = ipc_store.load()
	alive = ipc_store.is_joiner_alive()
	rows: list[list[InlineKeyboardButton]] = []
	if alive and state.status != "online":
		rows.append(
			[InlineKeyboardButton(text="📲 Подключить по номеру", callback_data="target_joiner:login")]
		)
	if alive and state.status == "online":
		rows.append(
			[InlineKeyboardButton(text="🚪 Отключить аккаунт", callback_data="target_joiner:logout")]
		)
	rows.append(
		[InlineKeyboardButton(text="🔄 Обновить статус", callback_data="target_joiner:menu")]
	)
	rows.append([InlineKeyboardButton(text="« Назад", callback_data="menu:account")])
	return InlineKeyboardMarkup(inline_keyboard=rows)


def _status_text() -> str:
	state = ipc_store.load()
	alive = ipc_store.is_joiner_alive()
	label = ipc_store.status_label()
	lines = [
		"<b>🔗 Инвайт-аккаунт</b>",
		"",
		"Скрипт сам принимает приглашения в группы/каналы,",
		"пока идёт перенос с лендинга.",
		"",
		f"• Скрипт: <b>{'работает' if alive else 'не запущен'}</b>",
		f"• Статус: <code>{label}</code>",
	]
	if state.me_id:
		who = f"@{state.me_username}" if state.me_username else state.me_name or str(state.me_id)
		phone = f"+{state.me_phone}" if state.me_phone else "—"
		lines.append(f"• Аккаунт: <code>{who}</code>")
		lines.append(f"• Телефон: <code>{phone}</code>")
	if state.error:
		lines.append(f"• Ошибка: <code>{state.error}</code>")
	if not alive:
		lines.extend(
			[
				"",
				"Запустите в отдельном терминале:",
				"<code>python target_invite_joiner.py</code>",
				"затем нажмите «Подключить по номеру».",
			]
		)
	elif state.status in {"idle", "error", "offline"}:
		lines.extend(["", "Нажмите «Подключить по номеру» и введите телефон целевого аккаунта."])
	return "\n".join(lines)


async def _wait_status(
	*,
	want: set[str],
	cmd_id: str,
	timeout: float = 45.0,
) -> str:
	deadline = asyncio.get_running_loop().time() + timeout
	while asyncio.get_running_loop().time() < deadline:
		state = ipc_store.load()
		if state.processed_cmd_id == cmd_id or state.status in want or state.status == "error":
			if state.status in want or state.status == "error":
				return state.status
			if state.processed_cmd_id == cmd_id and state.status in want | {"error", "online", "waiting_code", "waiting_password", "idle"}:
				return state.status
		await asyncio.sleep(0.5)
	return "timeout"


@router.callback_query(F.data == "target_joiner:menu")
async def cb_menu(callback: CallbackQuery, state: FSMContext) -> None:
	await state.clear()
	if ipc_store.is_joiner_alive():
		ipc_store.enqueue("ping")
		await asyncio.sleep(0.9)
	await callback.message.edit_text(
		_status_text(),
		reply_markup=_joiner_keyboard(),
		parse_mode="HTML",
	)
	await callback.answer()


@router.callback_query(F.data == "target_joiner:login")
async def cb_login(callback: CallbackQuery, state: FSMContext) -> None:
	if not ipc_store.is_joiner_alive():
		await callback.answer("Сначала запустите target_invite_joiner.py", show_alert=True)
		return
	await state.set_state(TargetJoinerStates.waiting_phone)
	await callback.message.edit_text(
		"Введите телефон целевого аккаунта в формате <code>+79001234567</code>",
		reply_markup=cancel_keyboard("target_joiner:menu"),
		parse_mode="HTML",
	)
	await callback.answer()


@router.callback_query(F.data == "target_joiner:logout")
async def cb_logout(callback: CallbackQuery, state: FSMContext) -> None:
	await state.clear()
	if not ipc_store.is_joiner_alive():
		await callback.answer("Скрипт не запущен", show_alert=True)
		return
	cmd = ipc_store.enqueue("logout")
	await callback.answer("Отключаем…")
	await _wait_status(want={"idle"}, cmd_id=cmd.cmd_id, timeout=30)
	await callback.message.edit_text(
		_status_text(),
		reply_markup=_joiner_keyboard(),
		parse_mode="HTML",
	)


@router.message(TargetJoinerStates.waiting_phone)
async def on_phone(message: Message, state: FSMContext) -> None:
	phone = (message.text or "").strip().replace(" ", "")
	if not _PHONE_RE.match(phone):
		await message.answer("Нужен номер вида <code>+79001234567</code>", parse_mode="HTML")
		return
	if not phone.startswith("+"):
		phone = "+" + phone
	if not ipc_store.is_joiner_alive():
		await message.answer("Скрипт joiner не запущен.")
		await state.clear()
		return

	await state.update_data(phone=phone)
	cmd = ipc_store.enqueue("login_phone", phone=phone)
	wait = await message.answer("Отправляю код…")
	status = await _wait_status(
		want={"waiting_code", "waiting_password", "online"},
		cmd_id=cmd.cmd_id,
	)
	cur = ipc_store.load()
	if status == "timeout":
		await wait.edit_text("Таймаут — проверьте, что joiner запущен.")
		await state.clear()
		return
	if status == "error":
		await wait.edit_text(f"Ошибка: <code>{cur.error or status}</code>", parse_mode="HTML")
		await state.clear()
		return
	if status == "online":
		await _finish_online(message, state, wait)
		return

	await state.set_state(TargetJoinerStates.waiting_code)
	await wait.edit_text(
		f"Код отправлен на <code>{phone}</code>.\nВведите код из Telegram:",
		parse_mode="HTML",
	)


@router.message(TargetJoinerStates.waiting_code)
async def on_code(message: Message, state: FSMContext) -> None:
	code = (message.text or "").strip().replace(" ", "")
	if not code.isdigit():
		await message.answer("Код — только цифры")
		return
	data = await state.get_data()
	phone = str(data.get("phone") or ipc_store.load().phone or "")
	cmd = ipc_store.enqueue("login_code", phone=phone, code=code)
	wait = await message.answer("Проверяю код…")
	status = await _wait_status(
		want={"waiting_password", "online"},
		cmd_id=cmd.cmd_id,
	)
	cur = ipc_store.load()
	if status == "timeout":
		await wait.edit_text("Таймаут ответа joiner.")
		await state.clear()
		return
	if status == "error":
		await wait.edit_text(f"Ошибка: <code>{cur.error or status}</code>", parse_mode="HTML")
		await state.set_state(TargetJoinerStates.waiting_code)
		return
	if status == "waiting_password":
		await state.set_state(TargetJoinerStates.waiting_password)
		await wait.edit_text("Введите облачный пароль 2FA этого аккаунта:")
		return
	await _finish_online(message, state, wait)


@router.message(TargetJoinerStates.waiting_password)
async def on_password(message: Message, state: FSMContext) -> None:
	password = message.text or ""
	if not password.strip():
		await message.answer("Пароль пустой")
		return
	data = await state.get_data()
	phone = str(data.get("phone") or ipc_store.load().phone or "")
	cmd = ipc_store.enqueue("login_password", phone=phone, password=password)
	try:
		await message.delete()
	except Exception:
		pass
	wait = await message.answer("Проверяю 2FA…")
	status = await _wait_status(want={"online"}, cmd_id=cmd.cmd_id)
	cur = ipc_store.load()
	if status != "online":
		await wait.edit_text(
			f"Не удалось войти: <code>{cur.error or status}</code>",
			parse_mode="HTML",
		)
		await state.clear()
		return
	await _finish_online(message, state, wait)


async def _finish_online(message: Message, state: FSMContext, status_msg: Message) -> None:
	await state.clear()
	cur = ipc_store.load()
	settings = await settings_repo.load()
	if cur.me_username:
		settings.target_username = cur.me_username
	elif cur.me_id:
		settings.target_username = str(cur.me_id)
	if cur.me_phone:
		settings.target_account = f"+{cur.me_phone.lstrip('+')}"
	elif cur.me_username:
		settings.target_account = f"@{cur.me_username}"
	await settings_repo.save(settings)

	who = f"@{cur.me_username}" if cur.me_username else cur.me_name or str(cur.me_id)
	await status_msg.edit_text(
		f"✅ Инвайт-аккаунт онлайн: <b>{who}</b>\n"
		f"Username для переноса: <code>{settings.target_username}</code>\n\n"
		"Теперь он сам будет вступать по ссылкам из миграции.",
		parse_mode="HTML",
		reply_markup=_joiner_keyboard(),
	)
