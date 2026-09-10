from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.handlers.site_ui import edit_site_panel, site_keyboard, site_summary
from bot.keyboards import cancel_keyboard
from landing.content_store import landing_store

router = Router()

_CANCEL = cancel_keyboard("site:show")


class SiteStates(StatesGroup):
	nick = State()
	username = State()
	bio = State()
	headline = State()
	location = State()
	stats = State()
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
	await edit_site_panel(callback)


@router.callback_query(F.data == "site:toggle_blur")
async def cb_blur(callback: CallbackQuery) -> None:
	c = await landing_store.load()
	await landing_store.update_fields(blur_until_login=not c.blur_until_login)
	await edit_site_panel(callback, answer="Сохранено")


@router.callback_query(F.data == "site:clear_photos")
async def cb_clear_photos(callback: CallbackQuery) -> None:
	await landing_store.clear_media("photos")
	await edit_site_panel(callback, answer="Фото очищены")


@router.callback_query(F.data == "site:clear_videos")
async def cb_clear_videos(callback: CallbackQuery) -> None:
	await landing_store.clear_media("videos")
	await edit_site_panel(callback, answer="Видео очищены")


@router.callback_query(F.data == "site:clear_socials")
async def cb_clear_socials(callback: CallbackQuery) -> None:
	await landing_store.clear_media("socials")
	await edit_site_panel(callback, answer="Соцсети очищены")


@router.callback_query(F.data == "site:nick")
async def cb_nick(callback: CallbackQuery, state: FSMContext) -> None:
	await state.set_state(SiteStates.nick)
	await callback.message.answer(
		"Введите отображаемое имя (Ashley):", reply_markup=_CANCEL
	)
	await callback.answer()


@router.callback_query(F.data == "site:username")
async def cb_username(callback: CallbackQuery, state: FSMContext) -> None:
	await state.set_state(SiteStates.username)
	await callback.message.answer(
		"Введите username без @ (ashleybaby):", reply_markup=_CANCEL
	)
	await callback.answer()


@router.callback_query(F.data == "site:bio")
async def cb_bio(callback: CallbackQuery, state: FSMContext) -> None:
	await state.set_state(SiteStates.bio)
	await callback.message.answer("Введите bio:", reply_markup=_CANCEL)
	await callback.answer()


@router.callback_query(F.data == "site:headline")
async def cb_headline(callback: CallbackQuery, state: FSMContext) -> None:
	await state.set_state(SiteStates.headline)
	await callback.message.answer(
		"Введите headline / статус под именем:", reply_markup=_CANCEL
	)
	await callback.answer()


@router.callback_query(F.data == "site:location")
async def cb_location(callback: CallbackQuery, state: FSMContext) -> None:
	await state.set_state(SiteStates.location)
	await callback.message.answer(
		"Введите локацию (или - чтобы очистить):", reply_markup=_CANCEL
	)
	await callback.answer()


@router.callback_query(F.data == "site:stats")
async def cb_stats(callback: CallbackQuery, state: FSMContext) -> None:
	await state.set_state(SiteStates.stats)
	await callback.message.answer(
		"Статистика одной строкой через |\n"
		"Формат: <code>лайки|фолловеры|фото|видео</code>\n"
		"Пример: <code>546.7K|130.3K|480|392</code>",
		parse_mode="HTML",
		reply_markup=_CANCEL,
	)
	await callback.answer()


@router.callback_query(F.data == "site:social")
async def cb_social(callback: CallbackQuery, state: FSMContext) -> None:
	await state.set_state(SiteStates.social_title)
	await callback.message.answer(
		"Название соцсети (Instagram / VK / OnlyFans...):",
		reply_markup=_CANCEL,
	)
	await callback.answer()


@router.callback_query(F.data == "site:avatar")
async def cb_avatar(callback: CallbackQuery, state: FSMContext) -> None:
	await state.set_state(SiteStates.waiting_avatar)
	await callback.message.answer(
		"Пришлите фото для аватара:", reply_markup=_CANCEL
	)
	await callback.answer()


@router.callback_query(F.data == "site:cover")
async def cb_cover(callback: CallbackQuery, state: FSMContext) -> None:
	await state.set_state(SiteStates.waiting_cover)
	await callback.message.answer(
		"Пришлите фото для обложки (header):", reply_markup=_CANCEL
	)
	await callback.answer()


@router.callback_query(F.data == "site:photo")
async def cb_photo(callback: CallbackQuery, state: FSMContext) -> None:
	await state.set_state(SiteStates.waiting_photo)
	await callback.message.answer(
		"Пришлите фото модели:", reply_markup=_CANCEL
	)
	await callback.answer()


@router.callback_query(F.data == "site:video")
async def cb_video(callback: CallbackQuery, state: FSMContext) -> None:
	await state.set_state(SiteStates.waiting_video)
	await callback.message.answer(
		"Пришлите видео (как файл или video):", reply_markup=_CANCEL
	)
	await callback.answer()


@router.message(SiteStates.nick)
async def set_nick(message: Message, state: FSMContext) -> None:
	await landing_store.update_fields(nick=(message.text or "").strip() or "Model")
	await state.clear()
	await message.answer("Имя сохранено.", reply_markup=await site_keyboard())


@router.message(SiteStates.username)
async def set_username(message: Message, state: FSMContext) -> None:
	raw = (message.text or "").strip().lstrip("@")
	await landing_store.update_fields(username=raw)
	await state.clear()
	await message.answer("Username сохранён.", reply_markup=await site_keyboard())


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


@router.message(SiteStates.location)
async def set_location(message: Message, state: FSMContext) -> None:
	raw = (message.text or "").strip()
	await landing_store.update_fields(location="" if raw == "-" else raw)
	await state.clear()
	await message.answer("Локация сохранена.", reply_markup=await site_keyboard())


@router.message(SiteStates.stats)
async def set_stats(message: Message, state: FSMContext) -> None:
	parts = [(p or "").strip() for p in (message.text or "").split("|")]
	while len(parts) < 4:
		parts.append("")
	await landing_store.update_fields(
		likes=parts[0],
		followers=parts[1],
		photos_stat=parts[2],
		videos_stat=parts[3],
	)
	await state.clear()
	await message.answer("Статистика сохранена.", reply_markup=await site_keyboard())


@router.message(SiteStates.social_title)
async def set_social_title(message: Message, state: FSMContext) -> None:
	await state.update_data(social_title=(message.text or "").strip() or "Link")
	await state.set_state(SiteStates.social_url)
	await message.answer("Теперь ссылку (https://...):", reply_markup=_CANCEL)


@router.message(SiteStates.social_url)
async def set_social_url(message: Message, state: FSMContext) -> None:
	data = await state.get_data()
	url = (message.text or "").strip()
	if not url.startswith("http"):
		await message.answer(
			"Ссылка должна начинаться с http", reply_markup=_CANCEL
		)
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
