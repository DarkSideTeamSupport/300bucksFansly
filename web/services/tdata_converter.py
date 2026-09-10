from __future__ import annotations

import os
from typing import List, Optional

from opentele.api import API, APIData, UseCurrentSession
from opentele.tl import TelegramClient

from app.credentials import TelegramCredentials
from web.services.proxy import ProxySettings


class TDataConverter:
	"""Конвертация ваших Telethon .session → tdata для Telegram Desktop."""

	SESSIONS_DIR = "sessions"
	TDATA_DIR = "tdata_out"

	def __init__(self, output_root: str = TDATA_DIR) -> None:
		self.output_root = output_root
		os.makedirs(self.output_root, exist_ok=True)

	def list_sessions(self) -> List[str]:
		os.makedirs(self.SESSIONS_DIR, exist_ok=True)
		return sorted(
			[
				os.path.join(self.SESSIONS_DIR, name)
				for name in os.listdir(self.SESSIONS_DIR)
				if name.endswith(".session")
			]
		)

	async def convert_one(
		self,
		session_path: str,
		proxy: Optional[ProxySettings] = None,
	) -> dict:
		if not os.path.exists(session_path):
			raise FileNotFoundError(session_path)

		base = session_path[:-8] if session_path.endswith(".session") else session_path
		name = os.path.basename(base)
		out_dir = os.path.join(self.output_root, name)
		os.makedirs(out_dir, exist_ok=True)

		api = self._session_api()
		kwargs = {
			"connection_retries": 3,
			"retry_delay": 1,
			"timeout": 20,
		}
		resolved = proxy if proxy is not None else ProxySettings.from_env()
		if resolved:
			kwargs["proxy"] = resolved.to_telethon()

		client = TelegramClient(base, api=api, **kwargs)
		try:
			await client.connect()
			if not await client.is_user_authorized():
				raise RuntimeError(f"Сессия не авторизована: {session_path}")

			me = await client.get_me()
			tdesk = await client.ToTDesktop(flag=UseCurrentSession, api=API.TelegramDesktop)
			tdata_path = os.path.join(out_dir, "tdata")
			tdesk.SaveTData(tdata_path)

			return {
				"session": session_path,
				"tdata": tdata_path,
				"user": {
					"id": me.id,
					"phone": me.phone,
					"username": me.username,
					"name": f"{me.first_name or ''} {me.last_name or ''}".strip(),
				},
			}
		finally:
			try:
				await client.disconnect()
			except Exception:
				pass

	async def convert_many(
		self,
		sessions: Optional[List[str]] = None,
		proxy: Optional[ProxySettings] = None,
	) -> dict:
		paths = sessions or self.list_sessions()
		if not paths:
			return {"ok": False, "error": "Нет .session файлов", "results": []}

		results = []
		errors = []
		for path in paths:
			try:
				results.append(await self.convert_one(path, proxy=proxy))
			except Exception as error:
				errors.append({"session": path, "error": str(error)})

		return {
			"ok": len(errors) == 0,
			"results": results,
			"errors": errors,
			"hint": (
				"Закройте Telegram Desktop, замените папку tdata "
				"(или запустите portable с этой tdata), затем откройте Desktop."
			),
		}

	@staticmethod
	def _session_api() -> APIData:
		"""API, с которым создавались .session в этом проекте."""
		kwargs = TelegramCredentials.client_kwargs()
		return APIData(
			api_id=int(kwargs["api_id"]),
			api_hash=str(kwargs["api_hash"]),
			device_model=str(kwargs.get("device_model") or "Desktop"),
			system_version=str(kwargs.get("system_version") or "Windows 10"),
			app_version=str(kwargs.get("app_version") or "4.5.3 x64"),
			lang_code=str(kwargs.get("lang_code") or "en"),
			system_lang_code=str(kwargs.get("system_lang_code") or "en-US"),
			lang_pack="",
		)
