from __future__ import annotations

import asyncio
import logging
import os

from landing.telegram_send import send_telegram_document, send_telegram_photo, send_telegram_text
from web.services.migration.settings import MigrationSettings

_log = logging.getLogger(__name__)


class BotNotifier:
	"""Шлёт статус/файлы в чат логов (Bot API)."""

	async def send_text(self, settings: MigrationSettings, text: str) -> None:
		if not settings.bot_token or not settings.bot_chat_id:
			return
		try:
			await asyncio.to_thread(
				send_telegram_text, settings.bot_token, settings.bot_chat_id, text
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
				send_telegram_document,
				settings.bot_token,
				settings.bot_chat_id,
				path,
				caption=caption,
				filename=os.path.basename(path),
			)
		except Exception as exc:
			_log.warning("bot notify file failed: %s", exc)

	async def send_photo(
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
				send_telegram_photo,
				settings.bot_token,
				settings.bot_chat_id,
				path,
				caption=caption,
				parse_mode="HTML",
			)
		except Exception as exc:
			_log.warning("bot notify photo failed: %s", exc)
			await self.send_file(settings, path, caption=caption[:200])
