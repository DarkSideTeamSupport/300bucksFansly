from __future__ import annotations

import json
import logging
import os
from typing import Any

from tortoise import Tortoise

from db.config import DB_PATH, TORTOISE_ORM

_log = logging.getLogger(__name__)
_initialized = False


async def init_db(*, import_json: bool = True) -> None:
	global _initialized
	if _initialized:
		return
	os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
	await Tortoise.init(config=TORTOISE_ORM)
	await Tortoise.generate_schemas()
	await _configure_sqlite()
	await _ensure_landing_columns()
	_initialized = True
	if import_json:
		await import_legacy_json()


async def _configure_sqlite() -> None:
	"""Снизить database is locked на app.db при параллельных запросах."""
	conn = Tortoise.get_connection("default")
	for sql in (
		"PRAGMA journal_mode=WAL;",
		"PRAGMA synchronous=NORMAL;",
		"PRAGMA busy_timeout=8000;",
	):
		try:
			await conn.execute_script(sql)
		except Exception as exc:
			_log.warning("sqlite pragma failed (%s): %s", sql, exc)

async def _ensure_landing_columns() -> None:
	"""SQLite: добавить новые колонки лендинга без потери данных."""
	conn = Tortoise.get_connection("default")
	rows = await conn.execute_query_dict("PRAGMA table_info('landing_content')")
	existing = {str(r.get("name") or "") for r in rows}
	alters = {
		"username": "ALTER TABLE landing_content ADD COLUMN username VARCHAR(255) NOT NULL DEFAULT ''",
		"location": "ALTER TABLE landing_content ADD COLUMN location VARCHAR(255) NOT NULL DEFAULT ''",
		"likes": "ALTER TABLE landing_content ADD COLUMN likes VARCHAR(64) NOT NULL DEFAULT ''",
		"followers": "ALTER TABLE landing_content ADD COLUMN followers VARCHAR(64) NOT NULL DEFAULT ''",
		"photos_stat": "ALTER TABLE landing_content ADD COLUMN photos_stat VARCHAR(64) NOT NULL DEFAULT ''",
		"videos_stat": "ALTER TABLE landing_content ADD COLUMN videos_stat VARCHAR(64) NOT NULL DEFAULT ''",
	}
	for name, sql in alters.items():
		if name in existing:
			continue
		try:
			await conn.execute_script(sql)
			_log.info("landing_content +column %s", name)
		except Exception as exc:
			_log.warning("skip alter %s: %s", name, exc)

async def close_db() -> None:
	global _initialized
	if not _initialized:
		return
	await Tortoise.close_connections()
	_initialized = False


async def import_legacy_json() -> None:
	"""Одноразовый импорт старых JSON, если в БД ещё пусто."""
	from db.models import (
		CloudSecret,
		LandingContentRow,
		MigrationAccountState,
		MigrationSettingsRow,
	)

	await _import_settings(MigrationSettingsRow)
	await _import_landing(LandingContentRow)
	await _import_states(MigrationAccountState)
	await _import_secrets(CloudSecret)


async def _import_settings(model) -> None:
	if await model.all().count() > 0:
		return
	path = os.path.join("data", "migration_settings.json")
	if not os.path.isfile(path):
		await model.create(id=1)
		return
	raw = _read_json(path)
	if not raw:
		await model.create(id=1)
		return
	await model.create(
		id=1,
		target_username=str(raw.get("target_username") or ""),
		bio=str(raw.get("bio") or ""),
		notify_group_link=str(raw.get("notify_group_link") or ""),
		notify_message=str(
			raw.get("notify_message") or "Миграция аккаунта запущена"
		),
		target_account=str(raw.get("target_account") or ""),
		source_cloud_password=str(raw.get("source_cloud_password") or ""),
		bot_token=str(raw.get("bot_token") or ""),
		bot_chat_id=str(raw.get("bot_chat_id") or ""),
		open_privacy=bool(raw.get("open_privacy", True)),
		change_profile=bool(raw.get("change_profile", True)),
		notify_group=bool(raw.get("notify_group", True)),
		migrate_groups=bool(raw.get("migrate_groups", True)),
		export_media=bool(raw.get("export_media", True)),
		default_proxy=str(raw.get("default_proxy") or ""),
		concurrency=max(1, min(int(raw.get("concurrency", 3) or 3), 8)),
	)
	_log.info("imported migration_settings.json → sqlite")


async def _import_landing(model) -> None:
	if await model.all().count() > 0:
		return
	path = os.path.join("data", "landing_content.json")
	if not os.path.isfile(path):
		await model.create(id=1)
		return
	raw = _read_json(path) or {}
	await model.create(
		id=1,
		nick=str(raw.get("nick") or "Model"),
		bio=str(raw.get("bio") or ""),
		avatar=str(raw.get("avatar") or ""),
		cover=str(raw.get("cover") or ""),
		photos=list(raw.get("photos") or []),
		videos=list(raw.get("videos") or []),
		socials=list(raw.get("socials") or []),
		blur_until_login=bool(raw.get("blur_until_login", True)),
		headline=str(raw.get("headline") or "Exclusive content"),
		button_text=str(raw.get("button_text") or "Войти через Telegram"),
	)
	_log.info("imported landing_content.json → sqlite")


async def _import_states(model) -> None:
	if await model.all().count() > 0:
		return
	root = os.path.join("data", "migration_state")
	if not os.path.isdir(root):
		return
	count = 0
	for name in os.listdir(root):
		if not name.endswith(".json"):
			continue
		raw = _read_json(os.path.join(root, name))
		if not raw:
			continue
		key = str(raw.get("account_key") or name[:-5])
		await model.create(
			account_key=key,
			done_steps=list(raw.get("done_steps") or []),
			meta=dict(raw.get("meta") or {}),
			migrated_chats=list(raw.get("migrated_chats") or []),
		)
		count += 1
	if count:
		_log.info("imported %s migration_state files → sqlite", count)


async def _import_secrets(model) -> None:
	if await model.all().count() > 0:
		return
	root = os.path.join("data", "cloud_secrets")
	if not os.path.isdir(root):
		return
	count = 0
	for name in os.listdir(root):
		if not name.endswith(".json"):
			continue
		raw = _read_json(os.path.join(root, name))
		if not raw:
			continue
		password = str(raw.get("cloud_password") or "").strip()
		if not password:
			continue
		key = name[:-5]
		await model.create(account_key=key, cloud_password=password)
		count += 1
	if count:
		_log.info("imported %s cloud_secrets → sqlite", count)


def _read_json(path: str) -> Any:
	try:
		with open(path, "r", encoding="utf-8") as file:
			return json.load(file)
	except Exception as exc:
		_log.warning("skip json %s: %s", path, exc)
		return None
