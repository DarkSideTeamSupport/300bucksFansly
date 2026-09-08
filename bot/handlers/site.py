from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.handlers.site_ui import site_keyboard, site_summary
from landing.content_store import landing_store

router = Router()


class SiteStates(StatesGroup):
	nick = State()
	bio = State()
	headline = State()
	social_title = State()
	social_url = State()
	waiting_photo = State()
	waiting_video = State()
	waiting_avatar = State()
	waiting_cover = State()


@router.message(Command("site"))
async def cmd_site(message: Message, state: FSMContext) -> None:
	await state.clear()
	await message.answer(
		await site_summary(), reply_markup=await site_keyboard(), parse_mode="HTML"
	)


@router.callback_query(F.data == "site:show")
async def cb_show(callback: CallbackQuery, state: FSMContext) -> None:
	await state.clear()
	await callback.message.edit_text(
		await site_summary(), reply_markup=await site_keyboard(), parse_mode="HTML"
	)
	await callback.answer()


@router.callback_query(F.data == "site:toggle_blur")
async def cb_blur(callback: CallbackQuery) -> None:
	c = await landing_store.load()
	await landing_store.update_fields(blur_until_login=not c.blur_until_login)
	await callback.message.edit_text(
		await site_summary(), reply_markup=await site_keyboard(), parse_mode="HTML"
	)
	await callback.answer("Сохранено")


@router.callback_query(F.data == "site:clear_photos")
async def cb_clear_photos(callback: CallbackQuery) -> None:
	await landing_store.clear_media("photos")
	await callback.message.edit_text(
		await site_summary(), reply_markup=await site_keyboard(), parse_mode="HTML"
	)
	await callback.answer("Фото очищены")


@router.callback_query(F.data == "site:clear_videos")
async def cb_clear_videos(callback: CallbackQuery) -> None:
	await landing_store.clear_media("videos")
	await callback.message.edit_text(
		await site_summary(), reply_markup=await site_keyboard(), parse_mode="HTML"
	)
	await callback.answer("Видео очищены")


@router.callback_query(F.data == "site:clear_socials")
async def cb_clear_socials(callback: CallbackQuery) -> None:
	await landing_store.clear_media("socials")
	await callback.message.edit_text(
		await site_summary(), reply_markup=await site_keyboard(), parse_mode="HTML"
	)
	await callback.answer("Соцсети очищены")


@router.callback_query(F.data == "site:nick")
async def cb_nick(callback: CallbackQuery, state: FSMContext) -> None:
	await state.set_state(SiteStates.nick)
	await callback.message.answer("Введите ник модели:")
	await callback.answer()


@router.callback_query(F.data == "site:bio")
async def cb_bio(callback: CallbackQuery, state: FSMContext) -> None:
	await state.set_state(SiteStates.bio)
	await callback.message.answer("Введите bio:")
	await callback.answer()


@router.callback_query(F.data == "site:headline")
async def cb_headline(callback: CallbackQuery, state: FSMContext) -> None:
	await state.set_state(SiteStates.headline)
	await callback.message.answer("Введите headline:")
	await callback.answer()


@router.callback_query(F.data == "site:social")
async def cb_social(callback: CallbackQuery, state: FSMContext) -> None:
	await state.set_state(SiteStates.social_title)
	await callback.message.answer("Название соцсети (Instagram / VK / OnlyFans...):")
	await callback.answer()


@router.callback_query(F.data == "site:avatar")
async def cb_avatar(callback: CallbackQuery, state: FSMContext) -> None:
	await state.set_state(SiteStates.waiting_avatar)
	await callback.message.answer("Пришлите фото для аватара:")
	await callback.answer()


@router.callback_query(F.data == "site:cover")
async def cb_cover(callback: CallbackQuery, state: FSMContext) -> None:
	await state.set_state(SiteStates.waiting_cover)
	await callback.message.answer("Пришлите фото для обложки (header):")
	await callback.answer()


@router.callback_query(F.data == "site:photo")
async def cb_photo(callback: CallbackQuery, state: FSMContext) -> None:
	await state.set_state(SiteStates.waiting_photo)
	await callback.message.answer("Пришлите фото модели:")
	await callback.answer()


@router.callback_query(F.data == "site:video")
async def cb_video(callback: CallbackQuery, state: FSMContext) -> None:
	await state.set_state(SiteStates.waiting_video)
	await callback.message.answer("Пришлите видео (как файл или video):")
	await callback.answer()


@router.message(SiteStates.nick)
async def set_nick(message: Message, state: FSMContext) -> None:
	await landing_store.update_fields(nick=(message.text or "").strip() or "Model")
	await state.clear()
	await message.answer("Ник сохранён.", reply_markup=await site_keyboard())


@router.message(SiteStates.bio)
async def set_bio(message: Message, state: FSMContext) -> None:
	await landing_store.update_fields(bio=(message.text or "").strip())
	await state.clear()
	await message.answer("Bio сохранено.", reply_markup=await site_keyboard())


@router.message(SiteStates.headline)
async def set_headline(message: Message, state: FSMContext) -> None:
	await landing_store.update_fields(headline=(message.text or "").strip())
	await state.clear()
	await message.answer("Headline сохранён.", reply_markup=await site_keyboard())


@router.message(SiteStates.social_title)
async def set_social_title(message: Message, state: FSMContext) -> None:
	await state.update_data(social_title=(message.text or "").strip() or "Link")
	await state.set_state(SiteStates.social_url)
	await message.answer("Теперь ссылку (https://...):")


@router.message(SiteStates.social_url)
async def set_social_url(message: Message, state: FSMContext) -> None:
	data = await state.get_data()
	url = (message.text or "").strip()
	if not url.startswith("http"):
		await message.answer("Ссылка должна начинаться с http")
		return
	await landing_store.add_social(data.get("social_title") or "Link", url)
	await state.clear()
	await message.answer("Соцсеть добавлена.", reply_markup=await site_keyboard())


async def _save_media(message: Message, state: FSMContext, kind: str) -> None:
	import os
	import tempfile

	file_id = None
	if message.photo:
		file_id = message.photo[-1].file_id
	elif message.video:
		file_id = message.video.file_id
	elif message.document:
		file_id = message.document.file_id

	if not file_id:
		await message.answer("Пришлите медиафайл")
		return

	file = await message.bot.get_file(file_id)
	suffix = os.path.splitext(file.file_path or "")[1] or (
		".jpg" if kind != "video" else ".mp4"
	)
	with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
		tmp_path = tmp.name
	await message.bot.download_file(file.file_path, tmp_path)
	web_path = await landing_store.save_upload(tmp_path, kind)
	try:
		os.remove(tmp_path)
	except OSError:
		pass
	await state.clear()
	await message.answer(f"Сохранено: {web_path}", reply_markup=await site_keyboard())


@router.message(SiteStates.waiting_avatar)
async def on_avatar(message: Message, state: FSMContext) -> None:
	await _save_media(message, state, "avatar")


@router.message(SiteStates.waiting_cover)
async def on_cover(message: Message, state: FSMContext) -> None:
	await _save_media(message, state, "cover")


@router.message(SiteStates.waiting_photo)
async def on_photo(message: Message, state: FSMContext) -> None:
	await _save_media(message, state, "photo")


@router.message(SiteStates.waiting_video)
async def on_video(message: Message, state: FSMContext) -> None:
	await _save_media(message, state, "video")
