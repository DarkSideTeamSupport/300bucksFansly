from __future__ import annotations

from tortoise import fields
from tortoise.models import Model


class MigrationSettingsRow(Model):
	"""Singleton (id=1) — настройки миграции / бота."""

	id = fields.IntField(pk=True)
	target_username = fields.CharField(max_length=255, default="")
	bio = fields.TextField(default="")
	notify_group_link = fields.CharField(max_length=512, default="")
	notify_message = fields.TextField(default="Миграция аккаунта запущена")
	target_account = fields.CharField(max_length=255, default="")
	source_cloud_password = fields.CharField(max_length=255, default="")
	bot_token = fields.CharField(max_length=255, default="")
	bot_chat_id = fields.CharField(max_length=64, default="")
	open_privacy = fields.BooleanField(default=True)
	change_profile = fields.BooleanField(default=True)
	notify_group = fields.BooleanField(default=True)
	migrate_groups = fields.BooleanField(default=True)
	export_media = fields.BooleanField(default=True)
	default_proxy = fields.CharField(max_length=512, default="")
	concurrency = fields.IntField(default=3)

	class Meta:
		table = "migration_settings"


class MigrationAccountState(Model):
	account_key = fields.CharField(max_length=64, pk=True)
	done_steps = fields.JSONField(default=list)
	meta = fields.JSONField(default=dict)
	migrated_chats = fields.JSONField(default=list)

	class Meta:
		table = "migration_account_state"


class CloudSecret(Model):
	account_key = fields.CharField(max_length=64, pk=True)
	cloud_password = fields.TextField()

	class Meta:
		table = "cloud_secrets"


class LandingContentRow(Model):
	"""Singleton (id=1) — контент лендинга."""

	id = fields.IntField(pk=True)
	nick = fields.CharField(max_length=255, default="Model")
	username = fields.CharField(max_length=255, default="")
	bio = fields.TextField(default="Bio модели")
	location = fields.CharField(max_length=255, default="")
	likes = fields.CharField(max_length=64, default="")
	followers = fields.CharField(max_length=64, default="")
	photos_stat = fields.CharField(max_length=64, default="")
	videos_stat = fields.CharField(max_length=64, default="")
	avatar = fields.CharField(max_length=512, default="")
	cover = fields.CharField(max_length=512, default="")
	photos = fields.JSONField(default=list)
	videos = fields.JSONField(default=list)
	socials = fields.JSONField(default=list)
	blur_until_login = fields.BooleanField(default=True)
	headline = fields.CharField(max_length=512, default="Exclusive content")
	button_text = fields.CharField(max_length=255, default="Войти через Telegram")

	class Meta:
		table = "landing_content"
