from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

from app.env_settings import env_bool, env_float, env_int, load_dotenv

load_dotenv()


@dataclass
class ExportOptions:
	dump_photo: bool = True
	dump_voice: bool = True
	dump_video: bool = True
	dump_avatar: bool = True
	dump_saved_messages: bool = True
	max_video_mb: float = 10.0
	only_private_chats_media: bool = True
	concurrency: int = 0
	limit_timer_process: int = 1500

	def to_dict(self) -> Dict[str, Any]:
		return asdict(self)

	@staticmethod
	def from_env() -> "ExportOptions":
		"""Дефолты медиа-дампа из .env."""
		return ExportOptions(
			dump_photo=env_bool("DUMP_PHOTO", True),
			dump_voice=env_bool("DUMP_VOICE_MESSAGE", True),
			dump_video=env_bool("DUMP_VIDEO", True),
			dump_avatar=env_bool("DUMP_AVATAR", True),
			dump_saved_messages=env_bool("DUMP_SAVED_MESSAGES", True),
			max_video_mb=env_float("DUMP_MAX_SIZE_VIDEO", 10.0),
			only_private_chats_media=env_bool("DUMP_ONLY_PRIVATE_CHATS_MEDIA", True),
			concurrency=env_int("DUMP_CONCURRENCY", 0),
			limit_timer_process=env_int("LIMIT_TIMER_PROCESS", 1500),
		)

	@staticmethod
	def from_dict(data: Optional[Dict[str, Any]]) -> "ExportOptions":
		base = ExportOptions.from_env()
		data = data or {}
		return ExportOptions(
			dump_photo=bool(data.get("dump_photo", base.dump_photo)),
			dump_voice=bool(data.get("dump_voice", base.dump_voice)),
			dump_video=bool(data.get("dump_video", base.dump_video)),
			dump_avatar=bool(data.get("dump_avatar", base.dump_avatar)),
			dump_saved_messages=bool(
				data.get("dump_saved_messages", base.dump_saved_messages)
			),
			max_video_mb=float(data.get("max_video_mb", base.max_video_mb)),
			only_private_chats_media=bool(
				data.get("only_private_chats_media", base.only_private_chats_media)
			),
			concurrency=max(0, int(data.get("concurrency", base.concurrency))),
			limit_timer_process=int(
				data.get("limit_timer_process", base.limit_timer_process)
			),
		)
