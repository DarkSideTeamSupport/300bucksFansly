from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
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
	"""Ограниченный параллельный запуск задач миграции/экспорта."""

	def __init__(self, concurrency: int = 3) -> None:
		self._concurrency = max(1, concurrency)
		self._semaphore = asyncio.Semaphore(self._concurrency)
		self._jobs: Dict[str, ExportJob] = {}

	def set_concurrency(self, value: int) -> None:
		value = max(1, min(value, 8))
		if value == self._concurrency:
			return
		self._concurrency = value
		self._semaphore = asyncio.Semaphore(value)

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
		async with self._semaphore:
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


job_runner = JobRunner(concurrency=3)
