from fastapi import APIRouter

from web.routes.auth_api import router as auth_router
from web.routes.jobs_api import router as jobs_router
from web.routes.settings_api import router as settings_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(settings_router)
router.include_router(jobs_router)
