from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from landing.content_store import landing_store


async def edit_site_panel(
	callback: CallbackQuery,
	*,
	answer: str | None = None,
) -> None:
	"""edit_text без падения, если контент/клавиатура не изменились."""
	try:
		await callback.message.edit_text(
			await site_summary(),
			reply_markup=await site_keyboard(),
			parse_mode="HTML",
		)
	except TelegramBadRequest as error:
		if "message is not modified" not in str(error):
			raise
	if answer is None:
		await callback.answer()
	else:
		await callback.answer(answer)


async def site_keyboard() -> InlineKeyboardMarkup:
	c = await landing_store.load()
	blur = "ON" if c.blur_until_login else "OFF"
	return InlineKeyboardMarkup(
		inline_keyboard=[
			[InlineKeyboardButton(text=f"Имя: {c.nick[:18]}", callback_data="site:nick")],
			[
				InlineKeyboardButton(
					text=f"Username: @{(c.username or c.handle)[:16]}",
					callback_data="site:username",
				)
			],
			[InlineKeyboardButton(text="Bio", callback_data="site:bio")],
			[InlineKeyboardButton(text="Headline / статус", callback_data="site:headline")],
			[
				InlineKeyboardButton(
					text=f"Локация: {(c.location or '—')[:16]}",
					callback_data="site:location",
				)
			],
			[
				InlineKeyboardButton(text="Аватар", callback_data="site:avatar"),
				InlineKeyboardButton(text="Обложка", callback_data="site:cover"),
			],
			[
				InlineKeyboardButton(text="＋ Фото", callback_data="site:photo"),
				InlineKeyboardButton(text="＋ Видео", callback_data="site:video"),
			],
			[InlineKeyboardButton(text="📊 Статистика (лайки…)", callback_data="site:stats")],
			[InlineKeyboardButton(text="＋ Соцсеть (X / IG…)", callback_data="site:social")],
			[
				InlineKeyboardButton(text="Очистить фото", callback_data="site:clear_photos"),
				InlineKeyboardButton(text="Очистить видео", callback_data="site:clear_videos"),
			],
			[InlineKeyboardButton(text="Очистить соцсети", callback_data="site:clear_socials")],
			[
				InlineKeyboardButton(
					text=f"Blur до логина: {blur}", callback_data="site:toggle_blur"
				)
			],
			[InlineKeyboardButton(text="Показать контент", callback_data="site:show")],
			[InlineKeyboardButton(text="« Назад", callback_data="menu:root")],
		]
	)


async def site_summary() -> str:
	c = await landing_store.load()
	socials = "\n".join(f"• {s['title']}: {s['url']}" for s in c.socials) or "—"
	return (
		"<b>🌐 Сайт / лендинг</b>\n\n"
		f"Имя: <code>{c.nick}</code>\n"
		f"Username: <code>@{c.handle}</code>\n"
		f"Headline: <code>{c.headline}</code>\n"
		f"Локация: <code>{c.location or '—'}</code>\n"
		f"Bio: <code>{(c.bio or '—')[:120]}</code>\n"
		f"Статы: ❤️ {c.display_likes} · 👥 {c.display_followers} · "
		f"📷 {c.display_photos} · 🎬 {c.display_videos}\n"
		f"Аватар: {'✅' if c.avatar else '—'}\n"
		f"Обложка: {'✅' if c.cover else '—'}\n"
		f"Фото файлов: {len(c.photos)}\n"
		f"Видео файлов: {len(c.videos)}\n"
		f"Blur: {'ON' if c.blur_until_login else 'OFF'}\n"
		f"Соцсети:\n{socials}"
	)
