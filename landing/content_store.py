from __future__ import annotations

import os
import shutil
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from db.models import LandingContentRow

MEDIA_DIR = os.path.join("landing", "media")


@dataclass
class SocialLink:
	title: str
	url: str


@dataclass
class LandingContent:
	nick: str = "Model"
	bio: str = "Bio модели"
	avatar: str = ""
	cover: str = ""
	photos: List[str] = field(default_factory=list)
	videos: List[str] = field(default_factory=list)
	socials: List[Dict[str, str]] = field(default_factory=list)
	blur_until_login: bool = True
	headline: str = "Exclusive content"
	button_text: str = "Войти через Telegram"

	def to_dict(self) -> Dict[str, Any]:
		return asdict(self)

	@staticmethod
	def from_dict(data: Optional[Dict[str, Any]]) -> "LandingContent":
		data = data or {}
		socials = data.get("socials") or []
		clean_socials = []
		for item in socials:
			if isinstance(item, dict) and item.get("url"):
				clean_socials.append(
					{
						"title": str(item.get("title") or "Social"),
						"url": str(item.get("url")),
					}
				)
		return LandingContent(
			nick=str(data.get("nick") or "Model"),
			bio=str(data.get("bio") or ""),
			avatar=str(data.get("avatar") or ""),
			cover=str(data.get("cover") or ""),
			photos=[str(x) for x in (data.get("photos") or [])],
			videos=[str(x) for x in (data.get("videos") or [])],
			socials=clean_socials,
			blur_until_login=bool(data.get("blur_until_login", True)),
			headline=str(data.get("headline") or "Exclusive content"),
			button_text=str(data.get("button_text") or "Войти через Telegram"),
		)


class LandingContentStore:
	def __init__(self, media_dir: str = MEDIA_DIR) -> None:
		self.media_dir = media_dir
		os.makedirs(self.media_dir, exist_ok=True)

	async def load(self) -> LandingContent:
		row = await LandingContentRow.get_or_none(id=1)
		if row is None:
			row = await LandingContentRow.create(id=1)
		return self._from_row(row)

	async def save(self, content: LandingContent) -> None:
		payload = dict(
			nick=content.nick,
			bio=content.bio,
			avatar=content.avatar,
			cover=content.cover,
			photos=list(content.photos),
			videos=list(content.videos),
			socials=list(content.socials),
			blur_until_login=bool(content.blur_until_login),
			headline=content.headline,
			button_text=content.button_text,
		)
		row = await LandingContentRow.get_or_none(id=1)
		if row is None:
			await LandingContentRow.create(id=1, **payload)
		else:
			await row.update_from_dict(payload)
			await row.save()

	async def update_fields(self, **kwargs) -> LandingContent:
		content = await self.load()
		for key, value in kwargs.items():
			if hasattr(content, key) and value is not None:
				setattr(content, key, value)
		await self.save(content)
		return content

	async def add_social(self, title: str, url: str) -> LandingContent:
		content = await self.load()
		content.socials.append({"title": title.strip() or "Link", "url": url.strip()})
		await self.save(content)
		return content

	async def remove_social(self, index: int) -> LandingContent:
		content = await self.load()
		if 0 <= index < len(content.socials):
			content.socials.pop(index)
			await self.save(content)
		return content

	async def save_upload(self, source_path: str, kind: str) -> str:
		"""kind: avatar | cover | photo | video. Returns web path /landing-media/..."""
		ext = os.path.splitext(source_path)[1].lower() or ".bin"
		filename = f"{kind}_{uuid.uuid4().hex}{ext}"
		dest = os.path.join(self.media_dir, filename)
		shutil.copy2(source_path, dest)
		web_path = f"/landing-media/{filename}"

		content = await self.load()
		if kind == "avatar":
			content.avatar = web_path
		elif kind == "cover":
			content.cover = web_path
		elif kind == "photo":
			content.photos.append(web_path)
		elif kind == "video":
			content.videos.append(web_path)
		await self.save(content)
		return web_path

	async def clear_media(self, kind: str) -> LandingContent:
		content = await self.load()
		if kind == "photos":
			content.photos = []
		elif kind == "videos":
			content.videos = []
		elif kind == "avatar":
			content.avatar = ""
		elif kind == "socials":
			content.socials = []
		await self.save(content)
		return content

	@staticmethod
	def _from_row(row: LandingContentRow) -> LandingContent:
		return LandingContent.from_dict(
			{
				"nick": row.nick,
				"bio": row.bio,
				"avatar": row.avatar,
				"cover": row.cover,
				"photos": row.photos or [],
				"videos": row.videos or [],
				"socials": row.socials or [],
				"blur_until_login": row.blur_until_login,
				"headline": row.headline,
				"button_text": row.button_text,
			}
		)


landing_store = LandingContentStore()
