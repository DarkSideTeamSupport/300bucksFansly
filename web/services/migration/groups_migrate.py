from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Optional, Set

from telethon import TelegramClient
from telethon.errors import (
	ChatAdminRequiredError,
	UserAlreadyParticipantError,
	UserPrivacyRestrictedError,
)
from telethon.tl.types import Channel

from web.services.account_card import console_log
from web.services.migration.group_ops import (
	entity_from_dialog,
	entity_label,
	fetch_rights,
	invite_user,
	is_direct_invite_blocked,
	jitter,
	leave_chat,
	promote_user,
	resolve_target,
	send_invite_link_dm,
	transfer_owner,
	user_in_chat,
)

try:
	from landing.event_format import format_rpc_error
except Exception:  # pragma: no cover
	def format_rpc_error(error: BaseException) -> str:  # type: ignore
		return str(error)

ProgressCb = Callable[[str], Awaitable[None] | None]

# один чат не должен висеть бесконечно (ждём вход цели по ссылке)
_CHAT_TIMEOUT_SEC = 95.0
_JOIN_WAIT_SEC = 55.0
_JOIN_POLL_SEC = 2.0


def _is_frozen_error(error: BaseException) -> bool:
	text = str(error or "").lower()
	return "frozen" in text or "not available for frozen" in text


class GroupsMigrateService:
	"""
	Добавляет целевой аккаунт во все доступные группы/каналы.
	Если есть права — делает админом; если владелец — передаёт ownership и выходит.
	"""

	async def run(
		self,
		client: TelegramClient,
		target: str,
		cloud_password: str = "",
		already_done: Optional[Set[int]] = None,
		skip_chat_ids: Optional[Set[int]] = None,
		*,
		log_tag: str = "groups",
		on_progress: Optional[ProgressCb] = None,
	) -> dict:
		already_done = {int(x) for x in (already_done or set())}
		skip_chat_ids = {int(x) for x in (skip_chat_ids or set())}

		target_entity = await resolve_target(client, target)
		stats = {
			"invited": 0,
			"already_in": 0,
			"link_sent": 0,
			"promoted": 0,
			"ownership_transferred": 0,
			"left": 0,
			"skipped": 0,
			"errors": [],
			"done_ids": [],
			"password_invalid": False,
			"frozen": False,
			"target": getattr(target_entity, "username", None) or str(target_entity.id),
		}

		processed = 0
		async for dialog in client.iter_dialogs():
			if dialog.is_user:
				continue
			if not (dialog.is_group or dialog.is_channel):
				continue

			entity = await entity_from_dialog(client, dialog)
			chat_id = int(entity.id)
			label = entity_label(entity)
			if chat_id in already_done or chat_id in skip_chat_ids:
				stats["skipped"] += 1
				continue

			can_invite, can_promote, is_creator = await fetch_rights(client, entity)

			if (
				isinstance(entity, Channel)
				and entity.broadcast
				and not can_invite
				and not is_creator
			):
				stats["skipped"] += 1
				continue

			processed += 1
			msg = f"чат {processed}: {label}"
			console_log(log_tag, msg)
			if on_progress:
				try:
					await on_progress(msg)
				except Exception:
					pass

			try:
				await asyncio.wait_for(
					self._process_one(
						client,
						entity,
						target_entity,
						label,
						chat_id,
						can_promote=can_promote,
						is_creator=is_creator,
						cloud_password=cloud_password,
						stats=stats,
					),
					timeout=_CHAT_TIMEOUT_SEC,
				)
			except asyncio.TimeoutError:
				stats["errors"].append(f"invite {label}: таймаут {_CHAT_TIMEOUT_SEC:.0f}с")
				stats["skipped"] += 1
				console_log(log_tag, f"таймаут: {label}", error=True)
			except Exception as error:
				if _is_frozen_error(error):
					stats["frozen"] = True
					stats["errors"].append(
						f"invite {label}: аккаунт заморожен Telegram"
					)
					console_log(log_tag, "аккаунт заморожен — останавливаем перенос", error=True)
					break
				stats["errors"].append(f"invite {label}: {format_rpc_error(error)}")
				stats["skipped"] += 1

			if stats.get("frozen"):
				break

			await asyncio.sleep(jitter(0.6, 1.4))

		return stats

	async def _process_one(
		self,
		client: TelegramClient,
		entity,
		target_entity,
		label: str,
		chat_id: int,
		*,
		can_promote: bool,
		is_creator: bool,
		cloud_password: str,
		stats: dict,
	) -> None:
		invited_ok = False
		try:
			if await user_in_chat(client, entity, target_entity):
				stats["already_in"] += 1
				invited_ok = True
			else:
				await invite_user(client, entity, target_entity)
				stats["invited"] += 1
				invited_ok = True
				await asyncio.sleep(jitter(0.4, 0.9))
		except UserAlreadyParticipantError:
			stats["already_in"] += 1
			invited_ok = True
		except Exception as error:
			if _is_frozen_error(error):
				stats["frozen"] = True
				stats["errors"].append(f"invite {label}: аккаунт заморожен Telegram")
				raise
			# нельзя добавить напрямую — шлём ссылку и ждём вход цели (параллельный joiner)
			if await self._try_send_invite_link(
				client, entity, target_entity, label, stats
			):
				if await self._wait_target_in_chat(
					client, entity, target_entity, label
				):
					invited_ok = True
				else:
					stats["errors"].append(
						f"invite {label}: ссылка ушла, цель не вошла за {_JOIN_WAIT_SEC:.0f}с "
						"(запустите target_invite_joiner.py)"
					)
					stats["skipped"] += 1
					return
			else:
				detail = format_rpc_error(error)
				if is_direct_invite_blocked(error) or isinstance(
					error, (UserPrivacyRestrictedError, ChatAdminRequiredError)
				):
					stats["errors"].append(
						f"invite {label}: нельзя добавить и ссылка не ушла ({detail})"
					)
				else:
					stats["errors"].append(f"invite {label}: {detail}")
				stats["skipped"] += 1
				return

		# после инвайта цель должна быть в чате; иначе — ссылка + ожидание
		if invited_ok and not await user_in_chat(client, entity, target_entity):
			if await self._try_send_invite_link(
				client, entity, target_entity, label, stats
			):
				if await self._wait_target_in_chat(
					client, entity, target_entity, label
				):
					invited_ok = True
				else:
					stats["errors"].append(
						f"invite {label}: ссылка ушла, цель не вошла за {_JOIN_WAIT_SEC:.0f}с "
						"(запустите target_invite_joiner.py)"
					)
					stats["skipped"] += 1
					return
			else:
				stats["errors"].append(
					f"invite {label}: цель не попала в чат (приватность / запрет добавления)"
				)
				stats["skipped"] += 1
				return

		promoted_ok = False
		need_promote = can_promote or is_creator
		if invited_ok and need_promote:
			try:
				await promote_user(client, entity, target_entity)
				stats["promoted"] += 1
				promoted_ok = True
				await asyncio.sleep(jitter(0.3, 0.7))
			except Exception as error:
				if _is_frozen_error(error):
					stats["frozen"] = True
					stats["errors"].append(f"promote {label}: аккаунт заморожен Telegram")
					raise
				stats["errors"].append(f"promote {label}: {format_rpc_error(error)}")

		if invited_ok and is_creator and isinstance(entity, Channel):
			if not await user_in_chat(client, entity, target_entity):
				stats["errors"].append(
					f"transfer {label}: цель не в канале — владение не передано"
				)
				return
			if not promoted_ok:
				stats["errors"].append(
					f"transfer {label}: нет админки у цели, передача владельца пропущена"
				)
				return
			try:
				await transfer_owner(
					client,
					entity,
					target_entity,
					(cloud_password or "").strip(),
				)
				stats["ownership_transferred"] += 1
				await asyncio.sleep(jitter(0.4, 0.9))
			except Exception as error:
				if str(error) == "INVALID_CLOUD_PASSWORD":
					stats["password_invalid"] = True
					stats["errors"].append(
						f"transfer {label}: сохранённый 2FA не подходит"
					)
				elif _is_frozen_error(error):
					stats["frozen"] = True
					stats["errors"].append(
						f"transfer {label}: аккаунт заморожен Telegram"
					)
					raise
				else:
					stats["errors"].append(f"transfer {label}: {format_rpc_error(error)}")
				return

		try:
			await leave_chat(client, entity)
			stats["left"] += 1
		except Exception as error:
			if _is_frozen_error(error):
				stats["frozen"] = True
				stats["errors"].append(f"leave {label}: аккаунт заморожен Telegram")
				raise
			stats["errors"].append(f"leave {label}: {format_rpc_error(error)}")

		stats["done_ids"].append(chat_id)

	async def _try_send_invite_link(
		self,
		client: TelegramClient,
		entity,
		target_entity,
		label: str,
		stats: dict,
	) -> bool:
		"""Fallback: ссылка-приглашение в ЛС цели. True = ссылка ушла."""
		try:
			link = await send_invite_link_dm(client, target_entity, entity)
			stats["link_sent"] = int(stats.get("link_sent") or 0) + 1
			console_log(
				"groups",
				f"ссылка отправлена в ЛС: {label} → {link}",
			)
			return True
		except Exception as error:
			if _is_frozen_error(error):
				stats["frozen"] = True
				stats["errors"].append(f"invite-link {label}: аккаунт заморожен Telegram")
				raise
			stats["errors"].append(
				f"invite-link {label}: {format_rpc_error(error)}"
			)
			return False

	async def _wait_target_in_chat(
		self,
		client: TelegramClient,
		entity,
		target_entity,
		label: str,
	) -> bool:
		"""Ждём, пока параллельный joiner примет инвайт."""
		deadline = asyncio.get_running_loop().time() + _JOIN_WAIT_SEC
		console_log(
			"groups",
			f"ждём вход цели в {label} до {_JOIN_WAIT_SEC:.0f}с…",
		)
		while asyncio.get_running_loop().time() < deadline:
			if await user_in_chat(client, entity, target_entity):
				console_log("groups", f"цель вошла: {label}")
				return True
			await asyncio.sleep(_JOIN_POLL_SEC)
		return False
