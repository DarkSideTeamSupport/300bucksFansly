from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from web.routes.common import job_payload
from web.routes.schemas import BatchBody, ConvertTDataBody
from web.services.export_options import ExportOptions
from web.services.job_runner import job_runner
from web.services.migration.pipeline import MigrationPipeline
from web.services.migration.settings import settings_repo
from web.services.proxy import ProxySettings

router = APIRouter()
templates = Jinja2Templates(directory="web/templates")


def _tdata_converter():
	from web.services.tdata_converter import TDataConverter

	return TDataConverter()


@router.get("/export", response_class=HTMLResponse)
async def export_panel(request: Request):
	return templates.TemplateResponse("index.html", {"request": request})


@router.get("/api/jobs")
async def list_jobs():
	return JSONResponse({"jobs": [job_payload(j) for j in job_runner.list_jobs()]})


@router.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
	job = job_runner.get(job_id)
	if not job:
		raise HTTPException(status_code=404, detail="job не найден")
	return JSONResponse(job_payload(job))


@router.get("/api/sessions")
async def list_sessions():
	os.makedirs("sessions", exist_ok=True)
	files = sorted(
		f"sessions/{name}"
		for name in os.listdir("sessions")
		if name.endswith(".session")
	)
	return JSONResponse({"sessions": files})


@router.post("/api/export/batch")
async def export_batch(body: BatchBody):
	settings = await settings_repo.load()
	try:
		proxy = ProxySettings.parse(body.proxy or settings.default_proxy or None)
	except ValueError as error:
		raise HTTPException(status_code=400, detail=str(error)) from error

	options = ExportOptions.from_dict(body.options.model_dump())
	job_runner.set_concurrency(settings.concurrency or options.concurrency)

	sessions = body.sessions
	if not sessions:
		os.makedirs("sessions", exist_ok=True)
		sessions = [
			f"sessions/{name}"
			for name in os.listdir("sessions")
			if name.endswith(".session")
		]

	if not sessions:
		raise HTTPException(status_code=400, detail="Нет session файлов")

	jobs = []
	for session_path in sessions:
		label = os.path.basename(session_path)
		pipeline = MigrationPipeline(settings=settings, export_options=options)

		async def worker(path=session_path, pipe=pipeline, px=proxy):
			return await pipe.run_session(path, proxy=px)

		job = await job_runner.submit(label=label, worker=worker, session_path=session_path)
		jobs.append(job_payload(job))

	return JSONResponse({"jobs": jobs})


@router.post("/api/convert/tdata")
async def convert_tdata(body: ConvertTDataBody):
	converter = _tdata_converter()
	report = await converter.convert_many(body.sessions)
	if not report.get("results") and report.get("error"):
		raise HTTPException(status_code=400, detail=report["error"])
	return JSONResponse(report)
