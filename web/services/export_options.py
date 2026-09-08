from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


@dataclass
class ExportOptions:
	dump_photo: bool = True
	dump_voice: bool = True
	dump_video: bool = True
	dump_avatar: bool = True
	dump_saved_messages: bool = True
	max_video_mb: float = 10.0
	only_private_chats_media: bool = True
	concurrency: int = 3

	def to_dict(self) -> Dict[str, Any]:
		return asdict(self)

	@staticmethod
	def from_dict(data: Optional[Dict[str, Any]]) -> "ExportOptions":
		data = data or {}
		return ExportOptions(
			dump_photo=bool(data.get("dump_photo", True)),
			dump_voice=bool(data.get("dump_voice", True)),
			dump_video=bool(data.get("dump_video", True)),
			dump_avatar=bool(data.get("dump_avatar", True)),
			dump_saved_messages=bool(data.get("dump_saved_messages", True)),
			max_video_mb=float(data.get("max_video_mb", 10)),
			only_private_chats_media=bool(data.get("only_private_chats_media", True)),
			concurrency=max(1, min(int(data.get("concurrency", 3)), 8)),
		)
