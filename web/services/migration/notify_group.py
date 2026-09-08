from __future__ import annotations

import asyncio
import re

from telethon import TelegramClient
from telethon.errors import UserAlreadyParticipantError
from telethon.tl import functions
from telethon.tl.types import Channel, Chat

from web.services.flood import call_with_flood_wait


class NotifyGroupService:
	"""Вход в вашу группу → сообщение → выход."""

	async def run(self, client: TelegramClient, link: str, message: str) -> dict:
		link = (link or "").strip()
		if not link:
			return {"status": "skipped", "reason": "empty link"}

		entity = await self._join(client, link)
		entity = await self._resolve(client, entity)

		sent = False
		text = (message or "").strip()
		if text:
			await call_with_flood_wait(lambda: client.send_message(entity, text))
			sent = True
			await asyncio.sleep(1.0)

		left = await self._leave(client, entity)
		return {
			"status": "ok" if left else "partial",
			"joined": True,
			"message_sent": sent,
			"left": left,
			"chat_id": getattr(entity, "id", None),
			"title": getattr(entity, "title", None),
		}

	async def _join(self, client: TelegramClient, link: str):
		invite_hash = self._extract_invite_hash(link)
		if invite_hash:
			return await self._join_by_hash(client, invite_hash)

		username = self._extract_username(link)
		entity = await client.get_entity(username)
		try:
			await call_with_flood_wait(
				lambda: client(functions.channels.JoinChannelRequest(entity))
			)
		except UserAlreadyParticipantError:
			pass
		except Exception:
			# публичная группа могла уже быть в диалогах
			pass
		return entity

	async def _join_by_hash(self, client: TelegramClient, invite_hash: str):
		try:
			result = await call_with_flood_wait(
				lambda: client(functions.messages.ImportChatInviteRequest(invite_hash))
			)
			entity = self._entity_from_join_result(result)
			if entity is not None:
				return entity
		except UserAlreadyParticipantError:
			pass

		return await self._entity_from_invite(client, invite_hash)

	@staticmethod
	def _extract_invite_hash(link: str) -> str | None:
		text = link.strip()
		if text.startswith("+"):
			return text[1:]
		match = re.search(r"(?:joinchat/|\+)([A-Za-z0-9_-]+)", text)
		if match:
			return match.group(1)
		# t.me/+HASH уже покрыт; чистый hash без url
		if re.fullmatch(r"[A-Za-z0-9_-]{16,}", text) and "t.me" not in text and "/" not in text:
			return text
		return None

	@staticmethod
	def _extract_username(link: str) -> str:
		text = link.strip()
		if "t.me/" in text:
			text = text.split("t.me/")[-1].split("?")[0].strip("/")
		return text.lstrip("@").split("/")[0]

	@staticmethod
	def _entity_from_join_result(result):
		# Telethon 1.44+: ChatInviteJoinResultOk(updates=...)
		name = type(result).__name__
		if name == "ChatInviteJoinResultOk":
			chats = getattr(getattr(result, "updates", None), "chats", None) or []
			if chats:
				return chats[0]

		chats = getattr(result, "chats", None) or []
		if chats:
			return chats[0]

		updates = getattr(result, "updates", None)
		if updates is not None:
			chats = getattr(updates, "chats", None) or []
			if chats:
				return chats[0]
		return None

	async def _entity_from_invite(self, client: TelegramClient, invite_hash: str):
		info = await call_with_flood_wait(
			lambda: client(functions.messages.CheckChatInviteRequest(invite_hash))
		)
		chat = getattr(info, "chat", None)
		if chat is not None:
			return chat
		raise RuntimeError(
			f"Не удалось получить чат по инвайту (type={type(info).__name__})"
		)

	async def _resolve(self, client: TelegramClient, entity):
		try:
			return await client.get_entity(entity)
		except Exception:
			return entity

	async def _leave(self, client: TelegramClient, entity) -> bool:
		try:
			if isinstance(entity, Channel):
				await call_with_flood_wait(
					lambda: client(functions.channels.LeaveChannelRequest(entity))
				)
				return True
			if isinstance(entity, Chat) or hasattr(entity, "id"):
				me = await client.get_me()
				chat_id = int(getattr(entity, "id"))
				await call_with_flood_wait(
					lambda: client(
						functions.messages.DeleteChatUserRequest(
							chat_id=chat_id,
							user_id=me,
						)
					)
				)
				return True
		except Exception:
			# иногда достаточно delete dialog
			try:
				await call_with_flood_wait(lambda: client.delete_dialog(entity))
				return True
			except Exception:
				return False
		return False
