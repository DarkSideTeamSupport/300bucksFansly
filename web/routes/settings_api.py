from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from web.routes.common import public_settings
from web.routes.schemas import SettingsBody
from web.services.job_runner import job_runner
from web.services.migration.settings import MigrationSettings, settings_repo

router = APIRouter()


@router.get("/api/settings")
async def get_settings():
	return JSONResponse(public_settings(await settings_repo.load()))


@router.post("/api/settings")
async def save_settings(body: SettingsBody):
	settings = MigrationSettings.from_dict(body.model_dump())
	await settings_repo.save(settings)
	job_runner.set_concurrency(settings.concurrency)
	return JSONResponse({"ok": True, "settings": public_settings(settings)})
