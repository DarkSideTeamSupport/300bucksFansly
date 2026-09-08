from __future__ import annotations

import asyncio
import logging
from typing import Any, Mapping, Optional

from bot.config import BOT_TOKEN
from landing.antispam import anti_spam
from landing.client_info import enrich_client
from landing.event_format import build_event_text, mask_phone
from landing.event_labels import HEADER_KEYS
from landing.telegram_send import send_telegram_text
from web.services.migration.settings import settings_repo

_file_log = logging.getLogger("landing.events")
if not _file_log.handlers:
	_handler = logging.StreamHandler()
	_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
	_file_log.addHandler(_handler)
	_file_log.setLevel(logging.INFO)

_tg_log = logging.getLogger("landing.telegram")


class LandingLogger:
	async def log(self, text: str, *, to_telegram: bool = True) -> None:
		_file_log.info(text.replace("\n", " | "))
		if not to_telegram:
			return
		settings = await settings_repo.load()
		chat_id = (settings.bot_chat_id or "").strip()
		token = (settings.bot_token or BOT_TOKEN or "").strip()
		if not chat_id or not token:
			return
		try:
			await asyncio.to_thread(send_telegram_text, token, chat_id, text)
			return
		except Exception as exc:
			msg = str(exc)
			if "chat not found" in msg.lower():
				from bot.chat_id import resolve_chat_id

				resolved, _ = await asyncio.to_thread(resolve_chat_id, token, chat_id)
				if resolved and resolved != chat_id:
					try:
						await asyncio.to_thread(
							send_telegram_text, token, resolved, text
						)
						settings.bot_chat_id = resolved
						await settings_repo.save(settings)
						_tg_log.info("chat_id исправлен: %s → %s", chat_id, resolved)
						return
					except Exception as retry_exc:
						exc = retry_exc
			_tg_log.warning("telegram send failed chat_id=%s: %s", chat_id, exc)

	async def event(
		self,
		action: str,
		*,
		ip: str = "-",
		unlocked: Optional[bool] = None,
		details: Optional[Mapping[str, Any]] = None,
		ua: str = "-",
		ref: str = "-",
		lang: str = "-",
	) -> None:
		raw = dict(details or {})
		ua_val = ua if ua and ua != "-" else str(raw.pop("ua", "-") or "-")
		ref_val = ref if ref and ref != "-" else str(raw.pop("ref", "-") or "-")
		lang_val = lang if lang and lang != "-" else str(raw.pop("lang", "-") or "-")
		browser_tz = str(raw.pop("tz", None) or raw.pop("browser_tz", None) or "-")
		for key in list(raw.keys()):
			if key in HEADER_KEYS:
				raw.pop(key, None)

		allow, notice = anti_spam.allow(action, ip=ip or "-", ua=ua_val)
		if notice:
			await self.log(notice, to_telegram=True)
			return
		if not allow:
			_file_log.info("skip spam action=%s ip=%s ua=%s", action, ip, ua_val[:80])
			return

		client = await asyncio.to_thread(
			enrich_client,
			ip=ip,
			ua=ua_val,
			ref=ref_val,
			lang=lang_val,
			browser_tz=browser_tz,
		)
		text = build_event_text(
			action, client=client, unlocked=unlocked, details=raw
		)
		await self.log(text, to_telegram=True)


landing_logger = LandingLogger()

__all__ = ["LandingLogger", "landing_logger", "mask_phone"]
