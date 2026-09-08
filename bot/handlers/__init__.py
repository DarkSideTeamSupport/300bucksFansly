from aiogram import Dispatcher

from bot.handlers.settings import router as settings_router
from bot.handlers.site import router as site_router


def setup_routers(dp: Dispatcher) -> None:
	dp.include_router(settings_router)
	dp.include_router(site_router)
