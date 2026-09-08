from __future__ import annotations

import asyncio
import logging
import os
from urllib import error, parse, request

from web.services.migration.settings import MigrationSettings

_log = logging.getLogger(__name__)


class BotNotifier:
	"""Шлёт статус/файлы в вашего бота (Bot API)."""

	async def send_text(self, settings: MigrationSettings, text: str) -> None:
		if not settings.bot_token or not settings.bot_chat_id:
			return
		try:
			await asyncio.to_thread(
				self._send_message, settings.bot_token, settings.bot_chat_id, text
			)
		except Exception as exc:
			_log.warning("bot notify text failed: %s", exc)

	async def send_file(
		self,
		settings: MigrationSettings,
		path: str,
		caption: str = "",
	) -> None:
		if not settings.bot_token or not settings.bot_chat_id:
			return
		if not path or not os.path.exists(path):
			return
		try:
			await asyncio.to_thread(
				self._send_document,
				settings.bot_token,
				settings.bot_chat_id,
				path,
				caption,
			)
		except Exception as exc:
			_log.warning("bot notify file failed: %s", exc)

	@staticmethod
	def _send_message(token: str, chat_id: str, text: str) -> None:
		url = f"https://api.telegram.org/bot{token}/sendMessage"
		payload = parse.urlencode(
			{"chat_id": chat_id, "text": text[:4000]}
		).encode("utf-8")
		req = request.Request(url, data=payload, method="POST")
		_open(req, timeout=60)

	@staticmethod
	def _send_document(token: str, chat_id: str, path: str, caption: str) -> None:
		# multipart вручную — без лишних зависимостей
		boundary = "----TgExportBoundary"
		url = f"https://api.telegram.org/bot{token}/sendDocument"
		filename = os.path.basename(path)
		with open(path, "rb") as file:
			file_data = file.read()

		body = (
			f"--{boundary}\r\n"
			f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{chat_id}\r\n'
			f"--{boundary}\r\n"
			f'Content-Disposition: form-data; name="caption"\r\n\r\n{caption[:1000]}\r\n'
			f"--{boundary}\r\n"
			f'Content-Disposition: form-data; name="document"; filename="{filename}"\r\n'
			f"Content-Type: application/octet-stream\r\n\r\n"
		).encode("utf-8") + file_data + f"\r\n--{boundary}--\r\n".encode("utf-8")

		req = request.Request(
			url,
			data=body,
			method="POST",
			headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
		)
		_open(req, timeout=120)


def _open(req: request.Request, *, timeout: int) -> None:
	try:
		with request.urlopen(req, timeout=timeout) as resp:
			resp.read()
	except error.HTTPError as exc:
		body = ""
		try:
			body = exc.read().decode("utf-8", errors="replace")[:500]
		except Exception:
			pass
		raise RuntimeError(f"HTTP {exc.code}: {body or exc.reason}") from exc
