from __future__ import annotations

import json
import mimetypes
import os
from typing import Optional
from urllib import error, parse, request


def _opener():
	proxy = (os.getenv("BOT_PROXY") or os.getenv("HTTPS_PROXY") or "").strip()
	if not proxy:
		return request.build_opener()
	return request.build_opener(request.ProxyHandler({"http": proxy, "https": proxy}))


def send_telegram_text(token: str, chat_id: str, text: str) -> None:
	url = f"https://api.telegram.org/bot{token}/sendMessage"
	payload = parse.urlencode(
		{
			"chat_id": chat_id,
			"text": text[:3500],
			"disable_web_page_preview": "1",
		}
	).encode("utf-8")
	req = request.Request(url, data=payload, method="POST")
	try:
		with _opener().open(req, timeout=30) as resp:
			resp.read()
	except error.HTTPError as exc:
		body = ""
		try:
			body = exc.read().decode("utf-8", errors="replace")[:500]
		except Exception:
			pass
		raise RuntimeError(f"HTTP {exc.code}: {body or exc.reason}") from exc


def send_telegram_document(
	token: str,
	chat_id: str,
	file_path: str,
	*,
	caption: str = "",
	filename: Optional[str] = None,
) -> None:
	"""Отправка файла в чат логов через multipart/form-data."""
	path = os.path.abspath(file_path)
	if not os.path.isfile(path):
		raise FileNotFoundError(path)

	name = filename or os.path.basename(path)
	mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
	boundary = f"----TGDumper{os.urandom(8).hex()}"
	with open(path, "rb") as fh:
		file_bytes = fh.read()

	parts: list[bytes] = []

	def add_field(key: str, value: str) -> None:
		parts.append(
			(
				f"--{boundary}\r\n"
				f'Content-Disposition: form-data; name="{key}"\r\n\r\n'
				f"{value}\r\n"
			).encode("utf-8")
		)

	add_field("chat_id", str(chat_id))
	if caption:
		add_field("caption", caption[:900])

	parts.append(
		(
			f"--{boundary}\r\n"
			f'Content-Disposition: form-data; name="document"; filename="{name}"\r\n'
			f"Content-Type: {mime}\r\n\r\n"
		).encode("utf-8")
	)
	parts.append(file_bytes)
	parts.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))
	body = b"".join(parts)

	url = f"https://api.telegram.org/bot{token}/sendDocument"
	req = request.Request(
		url,
		data=body,
		method="POST",
		headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
	)
	try:
		with _opener().open(req, timeout=120) as resp:
			raw = resp.read().decode("utf-8", errors="replace")
			data = json.loads(raw) if raw else {}
			if not data.get("ok", True):
				raise RuntimeError(raw[:500] or "sendDocument failed")
	except error.HTTPError as exc:
		body_txt = ""
		try:
			body_txt = exc.read().decode("utf-8", errors="replace")[:500]
		except Exception:
			pass
		raise RuntimeError(f"HTTP {exc.code}: {body_txt or exc.reason}") from exc
