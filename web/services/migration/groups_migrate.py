from __future__ import annotations

import asyncio
from typing import Optional, Set

from telethon import TelegramClient
from telethon.errors import (
	ChatAdminRequiredError,
	UserAlreadyParticipantError,
	UserPrivacyRestrictedError,
)
from telethon.tl.types import Channel

from web.services.migration.group_ops import (
	entity_from_dialog,
	entity_label,
	fetch_rights,
	invite_user,
	jitter,
	leave_chat,
	promote_user,
	resolve_target,
	transfer_owner,
)


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
	) -> dict:
		already_done = {int(x) for x in (already_done or set())}
		skip_chat_ids = {int(x) for x in (skip_chat_ids or set())}

		target_entity = await resolve_target(client, target)
		stats = {
			"invited": 0,
			"already_in": 0,
			"promoted": 0,
			"ownership_transferred": 0,
			"left": 0,
			"skipped": 0,
			"errors": [],
			"done_ids": [],
			"password_invalid": False,
			"target": getattr(target_entity, "username", None) or str(target_entity.id),
		}

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

			# Канал, где мы точно не админ/владелец — нет смысла
			if (
				isinstance(entity, Channel)
				and entity.broadcast
				and not can_invite
				and not is_creator
			):
				stats["skipped"] += 1
				continue

			invited_ok = False
			try:
				await invite_user(client, entity, target_entity)
				stats["invited"] += 1
				invited_ok = True
				await asyncio.sleep(jitter(1.0, 2.2))
			except UserAlreadyParticipantError:
				stats["already_in"] += 1
				invited_ok = True
			except (ChatAdminRequiredError, UserPrivacyRestrictedError) as error:
				stats["errors"].append(
					f"invite {label}: {error.__class__.__name__}"
				)
				stats["skipped"] += 1
				continue
			except Exception as error:
				stats["errors"].append(f"invite {label}: {error}")
				stats["skipped"] += 1
				continue

			promoted_ok = False
			# для передачи владельца promote обязателен
			need_promote = can_promote or is_creator
			if invited_ok and need_promote:
				try:
					await promote_user(client, entity, target_entity)
					stats["promoted"] += 1
					promoted_ok = True
					await asyncio.sleep(jitter(0.8, 1.6))
				except Exception as error:
					stats["errors"].append(f"promote {label}: {error}")

			if invited_ok and is_creator and isinstance(entity, Channel):
				if not promoted_ok:
					stats["errors"].append(
						f"transfer {label}: нет админки у цели, передача владельца пропущена"
					)
					# не выходим из канала-владельца, чтобы не потерять его
					continue
				try:
					await transfer_owner(
						client,
						entity,
						target_entity,
						(cloud_password or "").strip(),
					)
					stats["ownership_transferred"] += 1
					await asyncio.sleep(jitter(0.8, 1.8))
				except Exception as error:
					if str(error) == "INVALID_CLOUD_PASSWORD":
						stats["password_invalid"] = True
						stats["errors"].append(
							f"transfer {label}: сохранённый 2FA не подходит"
						)
					else:
						stats["errors"].append(f"transfer {label}: {error}")
					# не leave — иначе владелец потеряет канал
					continue

			try:
				await leave_chat(client, entity)
				stats["left"] += 1
			except Exception as error:
				stats["errors"].append(f"leave {label}: {error}")

			stats["done_ids"].append(chat_id)
			await asyncio.sleep(jitter(1.8, 4.2))

		return stats
