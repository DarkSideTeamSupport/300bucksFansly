from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any, Dict, Optional


class TelegramLoginVerifier:
	"""Проверка данных официального Telegram Login Widget (не Telethon-сессия)."""

	def __init__(self, bot_token: str, max_age_sec: int = 86400) -> None:
		self.bot_token = bot_token
		self.max_age_sec = max_age_sec

	def verify(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
		data = {str(k): str(v) for k, v in payload.items() if v is not None}
		received_hash = data.pop("hash", None)
		if not received_hash:
			return None

		check_list = [f"{k}={data[k]}" for k in sorted(data.keys())]
		check_string = "\n".join(check_list)
		secret_key = hashlib.sha256(self.bot_token.encode("utf-8")).digest()
		calculated = hmac.new(
			secret_key,
			check_string.encode("utf-8"),
			hashlib.sha256,
		).hexdigest()

		if not hmac.compare_digest(calculated, received_hash):
			return None

		auth_date = int(data.get("auth_date") or 0)
		if auth_date and abs(int(time.time()) - auth_date) > self.max_age_sec:
			return None

		return {
			"id": int(data["id"]),
			"first_name": data.get("first_name", ""),
			"last_name": data.get("last_name", ""),
			"username": data.get("username", ""),
			"photo_url": data.get("photo_url", ""),
			"auth_date": auth_date,
		}
