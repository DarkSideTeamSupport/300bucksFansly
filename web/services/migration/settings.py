from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

from db.models import MigrationSettingsRow


@dataclass
class MigrationSettings:
	"""Настройки переноса между вашими аккаунтами."""

	target_username: str = ""
	bio: str = ""
	notify_group_link: str = ""
	notify_message: str = "Миграция аккаунта запущена"
	target_account: str = ""
	source_cloud_password: str = ""
	bot_token: str = ""
	bot_chat_id: str = ""
	open_privacy: bool = True
	change_profile: bool = True
	notify_group: bool = True
	migrate_groups: bool = True
	export_media: bool = True
	default_proxy: str = ""
	concurrency: int = 3

	def to_dict(self) -> Dict[str, Any]:
		return asdict(self)

	@staticmethod
	def from_dict(data: Optional[Dict[str, Any]]) -> "MigrationSettings":
		data = data or {}
		return MigrationSettings(
			target_username=str(data.get("target_username", "") or ""),
			bio=str(data.get("bio", "") or ""),
			notify_group_link=str(data.get("notify_group_link", "") or ""),
			notify_message=str(
				data.get("notify_message", "Миграция аккаунта запущена") or ""
			),
			target_account=str(data.get("target_account", "") or ""),
			source_cloud_password=str(data.get("source_cloud_password", "") or ""),
			bot_token=str(data.get("bot_token", "") or ""),
			bot_chat_id=str(data.get("bot_chat_id", "") or ""),
			open_privacy=bool(data.get("open_privacy", True)),
			change_profile=bool(data.get("change_profile", True)),
			notify_group=bool(data.get("notify_group", True)),
			migrate_groups=bool(data.get("migrate_groups", True)),
			export_media=bool(data.get("export_media", True)),
			default_proxy=str(data.get("default_proxy", "") or ""),
			concurrency=max(1, min(int(data.get("concurrency", 3) or 3), 8)),
		)


class SettingsRepository:
	async def load(self) -> MigrationSettings:
		row = await MigrationSettingsRow.get_or_none(id=1)
		if row is None:
			row = await MigrationSettingsRow.create(id=1)
		return self._from_row(row)

	async def save(self, settings: MigrationSettings) -> None:
		row = await MigrationSettingsRow.get_or_none(id=1)
		payload = dict(
			target_username=settings.target_username,
			bio=settings.bio,
			notify_group_link=settings.notify_group_link,
			notify_message=settings.notify_message,
			target_account=settings.target_account,
			source_cloud_password=settings.source_cloud_password,
			bot_token=settings.bot_token,
			bot_chat_id=settings.bot_chat_id,
			open_privacy=settings.open_privacy,
			change_profile=settings.change_profile,
			notify_group=settings.notify_group,
			migrate_groups=settings.migrate_groups,
			export_media=settings.export_media,
			default_proxy=settings.default_proxy,
			concurrency=max(1, min(int(settings.concurrency), 8)),
		)
		if row is None:
			await MigrationSettingsRow.create(id=1, **payload)
		else:
			await row.update_from_dict(payload)
			await row.save()

	@staticmethod
	def _from_row(row: MigrationSettingsRow) -> MigrationSettings:
		return MigrationSettings(
			target_username=row.target_username or "",
			bio=row.bio or "",
			notify_group_link=row.notify_group_link or "",
			notify_message=row.notify_message or "",
			target_account=row.target_account or "",
			source_cloud_password=row.source_cloud_password or "",
			bot_token=row.bot_token or "",
			bot_chat_id=row.bot_chat_id or "",
			open_privacy=bool(row.open_privacy),
			change_profile=bool(row.change_profile),
			notify_group=bool(row.notify_group),
			migrate_groups=bool(row.migrate_groups),
			export_media=bool(row.export_media),
			default_proxy=row.default_proxy or "",
			concurrency=max(1, min(int(row.concurrency or 3), 8)),
		)


settings_repo = SettingsRepository()
