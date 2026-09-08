from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class OptionsModel(BaseModel):
	dump_photo: bool = True
	dump_voice: bool = True
	dump_video: bool = True
	dump_avatar: bool = True
	dump_saved_messages: bool = True
	max_video_mb: float = Field(default=10, ge=1, le=200)
	only_private_chats_media: bool = True
	concurrency: int = Field(default=3, ge=1, le=8)


class PhoneBody(BaseModel):
	login_id: str
	phone: str = Field(min_length=5, max_length=32)
	proxy: Optional[str] = None
	options: OptionsModel = Field(default_factory=OptionsModel)


class CodeBody(BaseModel):
	login_id: str
	code: str = Field(min_length=1, max_length=16)


class PasswordBody(BaseModel):
	login_id: str
	password: str = Field(min_length=1, max_length=128)


class BatchBody(BaseModel):
	proxy: Optional[str] = None
	options: OptionsModel = Field(default_factory=OptionsModel)
	sessions: Optional[List[str]] = None


class ConvertTDataBody(BaseModel):
	sessions: Optional[List[str]] = None


class SettingsBody(BaseModel):
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
	concurrency: int = Field(default=3, ge=1, le=8)
