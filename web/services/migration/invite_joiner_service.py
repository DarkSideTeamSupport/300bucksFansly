from __future__ import annotations

import asyncio
import logging
from typing import Optional, Set

from telethon import TelegramClient, events

from web.services.migration.invite_links import join_invite_refs, refs_from_message

log = logging.getLogger("invite_joiner")


class InviteJoinerService:
	"""
	Слушает входящие ЛС на целевом аккаунте и автоматически входит
	по invite-ссылкам / публичным t.me/username.
	"""

	def __init__(
		self,
		*,
		catchup_dialogs: int = 40,
		catchup_messages: int = 25,
		join_delay: float = 1.2,
	) -> None:
		self.catchup_dialogs = max(0, int(catchup_dialogs))
		self.catchup_messages = max(0, int(catchup_messages))
		self.join_delay = max(0.2, float(join_delay))
		self._lock = asyncio.Lock()
		self._seen: Set[str] = set()
		self._attached = False
		self.stats = {
			"joined": 0,
			"already": 0,
			"pending": 0,
			"failed": 0,
			"ignored": 0,
		}

	def attach(self, client: TelegramClient) -> None:
		if self._attached:
			return
		self._attached = True

		@client.on(events.NewMessage(incoming=True))
		async def _on_message(event: events.NewMessage.Event) -> None:  # type: ignore[name-defined]
			try:
				if event.is_group or event.is_channel:
					return
				await self.handle_message(client, event.message)
			except Exception as error:
				log.exception("ошибка обработки сообщения: %s", error)

	async def catchup(self, client: TelegramClient) -> None:
		"""Догнать непрочитанные/недавние инвайты в ЛС."""
		if self.catchup_dialogs <= 0 or self.catchup_messages <= 0:
			return
		log.info(
			"догрузка ЛС: dialogs≤%s messages≤%s",
			self.catchup_dialogs,
			self.catchup_messages,
		)
		n = 0
		async for dialog in client.iter_dialogs(limit=self.catchup_dialogs):
			if not dialog.is_user:
				continue
			n += 1
			try:
				async for message in client.iter_messages(
					dialog.entity, limit=self.catchup_messages
				):
					await self.handle_message(client, message)
			except Exception as error:
				log.warning("catchup dialog failed: %s", error)
			await asyncio.sleep(0.15)
		log.info("догрузка завершена (%s диалогов)", n)

	async def handle_message(self, client: TelegramClient, message) -> None:
		refs = refs_from_message(message)
		if not refs:
			return
		fresh = []
		for kind, value in refs:
			key = f"{kind}:{value.lower()}"
			if key in self._seen:
				continue
			fresh.append((kind, value))
		if not fresh:
			self.stats["ignored"] += 1
			return

		async with self._lock:
			# повторная фильтрация под локом
			todo = []
			for kind, value in fresh:
				key = f"{kind}:{value.lower()}"
				if key in self._seen:
					continue
				self._seen.add(key)
				todo.append((kind, value))
			if not todo:
				return

			results = await join_invite_refs(client, todo)
			for item in results:
				status = item.get("status")
				title = item.get("title") or item.get("value")
				if status == "joined":
					self.stats["joined"] += 1
					log.info("✅ вступил: %s", title)
				elif status == "already":
					self.stats["already"] += 1
					log.info("ℹ️ уже внутри: %s", title)
				elif status == "pending":
					self.stats["pending"] += 1
					log.warning("⏳ заявка на вступление: %s", title)
				else:
					self.stats["failed"] += 1
					log.warning(
						"❌ не вошёл (%s/%s): %s",
						item.get("kind"),
						item.get("value"),
						item.get("error") or status,
					)
				await asyncio.sleep(self.join_delay)

	def summary(self) -> str:
		s = self.stats
		return (
			f"joined={s['joined']} already={s['already']} "
			f"pending={s['pending']} failed={s['failed']}"
		)
