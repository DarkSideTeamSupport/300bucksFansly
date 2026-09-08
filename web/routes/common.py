from __future__ import annotations

from fastapi import Request

from web.services.migration.settings import MigrationSettings


def login_payload(state) -> dict:
	return {
		"login_id": state.login_id,
		"step": state.step.value,
		"error": state.error,
		"user_label": state.user_label,
		"session_path": state.session_path,
		"export_dir": state.export_dir,
		"job_id": state.job_id,
	}


def job_payload(job) -> dict:
	return {
		"job_id": job.job_id,
		"label": job.label,
		"status": job.status.value,
		"export_dir": job.export_dir,
		"error": job.error,
		"session_path": job.session_path,
		"result": job.result,
	}


def public_settings(settings: MigrationSettings) -> dict:
	return settings.to_dict()


def req_ip(request: Request | None) -> str:
	if request is None:
		return "-"
	forwarded = request.headers.get("x-forwarded-for")
	if forwarded:
		return forwarded.split(",")[0].strip()
	return request.client.host if request.client else "-"


def req_meta(request: Request | None) -> dict:
	if request is None:
		return {}
	return {
		"ua": request.headers.get("user-agent") or "-",
		"ref": request.headers.get("referer") or "-",
		"lang": (request.headers.get("accept-language") or "-")[:80],
	}
