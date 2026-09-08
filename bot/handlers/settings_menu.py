from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.handlers.settings_ui import edit_menu, format_settings, network_text, root_text
from bot.keyboards import (
	actions_keyboard,
	migration_keyboard,
	network_keyboard,
	profile_keyboard,
	root_keyboard,
	steps_keyboard,
)
from web.services.migration.settings import settings_repo

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
	await state.clear()
	await message.answer(await root_text(), reply_markup=root_keyboard(), parse_mode="HTML")


@router.message(Command("settings"))
async def cmd_settings(message: Message, state: FSMContext) -> None:
	await state.clear()
	await message.answer(
		await format_settings(),
		reply_markup=migration_keyboard(await settings_repo.load()),
		parse_mode="HTML",
	)


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext) -> None:
	await state.clear()
	await message.answer(await root_text(), reply_markup=root_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "menu:root")
async def cb_root(callback: CallbackQuery, state: FSMContext) -> None:
	await state.clear()
	await edit_menu(callback, await root_text(), root_keyboard())


@router.callback_query(F.data == "menu:migration")
async def cb_migration(callback: CallbackQuery, state: FSMContext) -> None:
	await state.clear()
	await edit_menu(
		callback,
		await format_settings(),
		migration_keyboard(await settings_repo.load()),
	)


@router.callback_query(F.data == "menu:profile")
async def cb_profile(callback: CallbackQuery, state: FSMContext) -> None:
	await state.clear()
	await edit_menu(
		callback,
		"<b>Профиль миграции</b>\nUsername, bio, целевой аккаунт.",
		profile_keyboard(await settings_repo.load()),
	)


@router.callback_query(F.data == "menu:network")
async def cb_network(callback: CallbackQuery, state: FSMContext) -> None:
	await state.clear()
	await edit_menu(
		callback,
		await network_text(),
		network_keyboard(await settings_repo.load()),
	)


@router.callback_query(F.data == "menu:steps")
async def cb_steps(callback: CallbackQuery, state: FSMContext) -> None:
	await state.clear()
	await edit_menu(
		callback,
		"<b>Шаги пайплайна</b>\nВкл/выкл этапы миграции.",
		steps_keyboard(await settings_repo.load()),
	)


@router.callback_query(F.data == "menu:actions")
async def cb_actions(callback: CallbackQuery, state: FSMContext) -> None:
	await state.clear()
	await edit_menu(callback, "<b>Действия</b>", actions_keyboard())


@router.callback_query(F.data == "menu:site")
async def cb_menu_site(callback: CallbackQuery, state: FSMContext) -> None:
	await state.clear()
	from bot.handlers.site import site_keyboard, site_summary

	await edit_menu(callback, await site_summary(), await site_keyboard())


@router.callback_query(F.data == "show")
async def cb_show(callback: CallbackQuery, state: FSMContext) -> None:
	await state.clear()
	await edit_menu(
		callback,
		await format_settings(),
		migration_keyboard(await settings_repo.load()),
	)


@router.callback_query(F.data == "cancel")
async def cb_cancel(callback: CallbackQuery, state: FSMContext) -> None:
	await state.clear()
	await edit_menu(
		callback,
		await format_settings(),
		migration_keyboard(await settings_repo.load()),
	)
