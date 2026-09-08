import asyncio
import logging

from aiogram import Bot, Dispatcher

from bot.config import BOT_TOKEN
from bot.handlers import setup_routers
from bot.middleware import AdminAccessMiddleware
from db import close_db, init_db
from web.services.migration.settings import settings_repo


async def main() -> None:
	logging.basicConfig(level=logging.INFO)
	await init_db()

	# тот же бот используется для отчётов пайплайна
	settings = await settings_repo.load()
	settings.bot_token = BOT_TOKEN
	await settings_repo.save(settings)

	bot = Bot(token=BOT_TOKEN)
	dp = Dispatcher()
	dp.message.middleware(AdminAccessMiddleware())
	dp.callback_query.middleware(AdminAccessMiddleware())
	setup_routers(dp)

	logging.info("Settings bot started")
	try:
		await dp.start_polling(bot)
	finally:
		await close_db()


if __name__ == "__main__":
	asyncio.run(main())
