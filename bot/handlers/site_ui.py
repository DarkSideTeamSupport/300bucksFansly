from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from landing.content_store import landing_store


async def site_keyboard() -> InlineKeyboardMarkup:
	c = await landing_store.load()
	blur = "ON" if c.blur_until_login else "OFF"
	return InlineKeyboardMarkup(
		inline_keyboard=[
			[
				InlineKeyboardButton(text=f"Ник: {c.nick[:16]}", callback_data="site:nick"),
				InlineKeyboardButton(text="Bio", callback_data="site:bio"),
			],
			[InlineKeyboardButton(text="Headline", callback_data="site:headline")],
			[
				InlineKeyboardButton(text="Аватар", callback_data="site:avatar"),
				InlineKeyboardButton(text="Обложка", callback_data="site:cover"),
			],
			[
				InlineKeyboardButton(text="＋ Фото", callback_data="site:photo"),
				InlineKeyboardButton(text="＋ Видео", callback_data="site:video"),
			],
			[InlineKeyboardButton(text="＋ Соцсеть", callback_data="site:social")],
			[
				InlineKeyboardButton(text="Очистить фото", callback_data="site:clear_photos"),
				InlineKeyboardButton(text="Очистить видео", callback_data="site:clear_videos"),
			],
			[InlineKeyboardButton(text="Очистить соцсети", callback_data="site:clear_socials")],
			[InlineKeyboardButton(text=f"Blur до логина: {blur}", callback_data="site:toggle_blur")],
			[InlineKeyboardButton(text="Показать контент", callback_data="site:show")],
			[InlineKeyboardButton(text="« Назад", callback_data="menu:root")],
		]
	)


async def site_summary() -> str:
	c = await landing_store.load()
	socials = "\n".join(f"• {s['title']}: {s['url']}" for s in c.socials) or "-"
	return (
		"<b>Контент лендинга</b>\n"
		f"Ник: <code>{c.nick}</code>\n"
		f"Headline: <code>{c.headline}</code>\n"
		f"Bio: <code>{c.bio}</code>\n"
		f"Аватар: {'yes' if c.avatar else 'no'}\n"
		f"Фото: {len(c.photos)}\n"
		f"Видео: {len(c.videos)}\n"
		f"Blur: {'ON' if c.blur_until_login else 'OFF'}\n"
		f"Соцсети:\n{socials}"
	)
