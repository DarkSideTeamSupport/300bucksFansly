from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[3]
IPC_PATH = ROOT / "data" / "target_joiner_ipc.json"


@dataclass
class TargetJoinerIpc:
	"""Общий файл между target_invite_joiner.py и ботом."""

	# команда от бота (joiner сбрасывает cmd после обработки)
	cmd: str = ""
	cmd_id: str = ""
	phone: str = ""
	code: str = ""
	password: str = ""

	# статус от joiner
	status: str = "offline"  # offline | idle | waiting_code | waiting_password | online | busy | error
	error: str = ""
	me_id: int = 0
	me_username: str = ""
	me_phone: str = ""
	me_name: str = ""
	joiner_alive_at: float = 0.0
	updated_at: float = 0.0
	processed_cmd_id: str = ""

	extra: dict[str, Any] = field(default_factory=dict)

	def to_dict(self) -> dict[str, Any]:
		data = asdict(self)
		return data

	@staticmethod
	def from_dict(raw: Optional[dict]) -> "TargetJoinerIpc":
		raw = raw or {}
		return TargetJoinerIpc(
			cmd=str(raw.get("cmd") or ""),
			cmd_id=str(raw.get("cmd_id") or ""),
			phone=str(raw.get("phone") or ""),
			code=str(raw.get("code") or ""),
			password=str(raw.get("password") or ""),
			status=str(raw.get("status") or "offline"),
			error=str(raw.get("error") or ""),
			me_id=int(raw.get("me_id") or 0),
			me_username=str(raw.get("me_username") or ""),
			me_phone=str(raw.get("me_phone") or ""),
			me_name=str(raw.get("me_name") or ""),
			joiner_alive_at=float(raw.get("joiner_alive_at") or 0),
			updated_at=float(raw.get("updated_at") or 0),
			processed_cmd_id=str(raw.get("processed_cmd_id") or ""),
			extra=dict(raw.get("extra") or {}),
		)


class TargetJoinerIpcStore:
	def __init__(self, path: Path | None = None) -> None:
		self.path = path or IPC_PATH

	def load(self) -> TargetJoinerIpc:
		if not self.path.is_file():
			return TargetJoinerIpc()
		try:
			raw = json.loads(self.path.read_text(encoding="utf-8"))
			if not isinstance(raw, dict):
				return TargetJoinerIpc()
			return TargetJoinerIpc.from_dict(raw)
		except Exception:
			return TargetJoinerIpc()

	def save(self, state: TargetJoinerIpc) -> None:
		state.updated_at = time.time()
		self.path.parent.mkdir(parents=True, exist_ok=True)
		tmp = self.path.with_suffix(".tmp")
		payload = json.dumps(state.to_dict(), ensure_ascii=False, indent=2)
		tmp.write_text(payload, encoding="utf-8")
		os.replace(tmp, self.path)

	def heartbeat(self, *, status: str | None = None, error: str = "") -> TargetJoinerIpc:
		state = self.load()
		state.joiner_alive_at = time.time()
		if status:
			state.status = status
		if error:
			state.error = error
		elif status and status != "error":
			state.error = ""
		self.save(state)
		return state

	def set_me(self, me) -> TargetJoinerIpc:
		state = self.load()
		state.me_id = int(getattr(me, "id", 0) or 0)
		state.me_username = str(getattr(me, "username", None) or "")
		state.me_phone = str(getattr(me, "phone", None) or "")
		first = str(getattr(me, "first_name", None) or "")
		last = str(getattr(me, "last_name", None) or "")
		state.me_name = (first + " " + last).strip()
		state.status = "online"
		state.error = ""
		state.joiner_alive_at = time.time()
		self.save(state)
		return state

	def clear_me(self, *, status: str = "idle") -> TargetJoinerIpc:
		state = self.load()
		state.me_id = 0
		state.me_username = ""
		state.me_phone = ""
		state.me_name = ""
		state.status = status
		state.joiner_alive_at = time.time()
		self.save(state)
		return state

	def enqueue(
		self,
		cmd: str,
		*,
		phone: str = "",
		code: str = "",
		password: str = "",
	) -> TargetJoinerIpc:
		state = self.load()
		state.cmd = cmd
		state.cmd_id = uuid.uuid4().hex
		state.phone = phone
		state.code = code
		state.password = password
		state.error = ""
		if cmd in {"login_phone", "login_code", "login_password", "logout"}:
			state.status = "busy"
		self.save(state)
		return state

	def ack_cmd(self, cmd_id: str) -> TargetJoinerIpc:
		state = self.load()
		if state.cmd_id == cmd_id:
			state.cmd = ""
			state.code = ""
			state.password = ""
			# phone оставляем для следующего sign_in
			state.processed_cmd_id = cmd_id
		self.save(state)
		return state

	def is_joiner_alive(self, max_age_sec: float = 12.0) -> bool:
		state = self.load()
		if not state.joiner_alive_at:
			return False
		return (time.time() - float(state.joiner_alive_at)) <= max_age_sec

	def status_label(self) -> str:
		state = self.load()
		alive = self.is_joiner_alive()
		if not alive:
			return "скрипт выключен"
		if state.status == "online":
			if state.me_username:
				return f"@{state.me_username}"
			if state.me_phone:
				return f"+{state.me_phone.lstrip('+')}"
			if state.me_id:
				return f"id:{state.me_id}"
			return "онлайн"
		labels = {
			"idle": "ждёт логин",
			"waiting_code": "ждёт код",
			"waiting_password": "ждёт 2FA",
			"busy": "занят…",
			"error": "ошибка",
			"offline": "оффлайн",
		}
		return labels.get(state.status, state.status)


ipc_store = TargetJoinerIpcStore()
