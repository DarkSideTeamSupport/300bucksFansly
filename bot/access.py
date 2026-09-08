from __future__ import annotations

import os
from typing import FrozenSet

from bot.config import load_dotenv

load_dotenv()


def parse_admin_chat_ids(raw: str | None = None) -> FrozenSet[int]:
	text = (raw if raw is not None else os.getenv("ADMIN_CHAT_IDS", "")).strip()
	ids: set[int] = set()
	for part in text.replace(";", ",").split(","):
		part = part.strip()
		if not part:
			continue
		try:
			ids.add(int(part))
		except ValueError:
			continue
	return frozenset(ids)


async def allowed_chat_ids() -> FrozenSet[int]:
	"""Разрешённые chat_id: ADMIN_CHAT_IDS из .env + bot_chat_id из настроек."""
	ids = set(parse_admin_chat_ids())
	try:
		from web.services.migration.settings import settings_repo

		chat_id = ((await settings_repo.load()).bot_chat_id or "").strip()
		if chat_id.lstrip("-").isdigit():
			ids.add(int(chat_id))
	except Exception:
		pass
	return frozenset(ids)


async def is_allowed_chat(chat_id: int | None) -> bool:
	if chat_id is None:
		return False
	allowed = await allowed_chat_ids()
	if not allowed:
		# без allowlist бот закрыт — укажите ADMIN_CHAT_IDS в .env
		return False
	return int(chat_id) in allowed
