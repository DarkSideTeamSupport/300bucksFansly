from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional


class JobStatus(str, Enum):
	QUEUED = "queued"
	RUNNING = "running"
	DONE = "done"
	ERROR = "error"


@dataclass
class ExportJob:
	job_id: str
	label: str
	status: JobStatus = JobStatus.QUEUED
	export_dir: Optional[str] = None
	error: Optional[str] = None
	session_path: Optional[str] = None
	result: Optional[Dict[str, Any]] = None


class JobRunner:
	"""Параллельный запуск задач миграции/экспорта.

	concurrency=0 — без лимита (все джобы стартуют сразу).
	"""

	def __init__(self, concurrency: int = 0) -> None:
		self._concurrency = max(0, int(concurrency))
		self._semaphore: Optional[asyncio.Semaphore] = (
			None if self._concurrency == 0 else asyncio.Semaphore(self._concurrency)
		)
		self._jobs: Dict[str, ExportJob] = {}

	def set_concurrency(self, value: int) -> None:
		value = max(0, int(value))
		if value == self._concurrency:
			return
		self._concurrency = value
		self._semaphore = None if value == 0 else asyncio.Semaphore(value)

	@asynccontextmanager
	async def _slot(self):
		if self._semaphore is None:
			yield
			return
		async with self._semaphore:
			yield

	def list_jobs(self) -> List[ExportJob]:
		return list(self._jobs.values())

	def get(self, job_id: str) -> Optional[ExportJob]:
		return self._jobs.get(job_id)

	async def submit(
		self,
		label: str,
		worker: Callable[[], Awaitable[Any]],
		session_path: Optional[str] = None,
	) -> ExportJob:
		job = ExportJob(job_id=uuid.uuid4().hex, label=label, session_path=session_path)
		self._jobs[job.job_id] = job
		asyncio.create_task(self._run(job, worker))
		return job

	async def _run(self, job: ExportJob, worker: Callable[[], Awaitable[Any]]) -> None:
		async with self._slot():
			job.status = JobStatus.RUNNING
			try:
				result = await worker()
				if isinstance(result, str):
					job.export_dir = result
				elif isinstance(result, dict):
					job.result = result
					job.export_dir = result.get("export_dir")
				job.status = JobStatus.DONE
			except Exception as error:
				job.status = JobStatus.ERROR
				job.error = str(error)


job_runner = JobRunner(concurrency=0)
