from aiogram import Router

from bot.handlers.settings_actions import router as actions_router
from bot.handlers.settings_bind import router as bind_router
from bot.handlers.settings_fields import router as fields_router
from bot.handlers.settings_menu import router as menu_router
from bot.handlers.target_joiner import router as target_joiner_router

router = Router()
router.include_router(menu_router)
router.include_router(bind_router)
router.include_router(fields_router)
router.include_router(actions_router)
router.include_router(target_joiner_router)
