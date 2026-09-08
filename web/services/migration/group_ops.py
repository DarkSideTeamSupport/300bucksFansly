from __future__ import annotations

import random
import re
from typing import Optional

from telethon import TelegramClient
from telethon.password import compute_check
from telethon.tl import functions, types
from telethon.tl.types import Channel, Chat, User

from web.services.flood import call_with_flood_wait


def jitter(low: float, high: float) -> float:
	return random.uniform(low, high)


def normalize_target(raw: str) -> str:
	text = (raw or "").strip()
	if not text:
		return ""
	if text.startswith("@"):
		return text[1:]
	match = re.search(
		r"(?:https?://)?(?:t\.me|telegram\.(?:me|dog))/([A-Za-z0-9_]{4,})",
		text,
		flags=re.I,
	)
	if match:
		username = match.group(1)
		if username.lower() not in {"joinchat", "addstickers", "share", "s"}:
			return username
	return text


async def resolve_target(client: TelegramClient, target: str) -> User:
	raw = normalize_target(target)
	if not raw:
		raise RuntimeError("target_account пустой")
	try:
		entity = await client.get_entity(raw)
	except Exception as error:
		raise RuntimeError(
			f"Не удалось найти целевой аккаунт «{raw}»: {error}. "
			"Укажите @username, с которого видит мигрирующий аккаунт "
			"(или добавьте его в контакты)."
		) from error
	if not isinstance(entity, User):
		raise RuntimeError(
			f"target_account должен быть пользователем, получено: {type(entity).__name__}"
		)
	if getattr(entity, "bot", False):
		raise RuntimeError("target_account не должен быть ботом")
	return entity


def chat_rights(entity) -> tuple[bool, bool, bool]:
	"""Быстрая оценка по полям entity (может быть неполной)."""
	if isinstance(entity, Channel):
		is_creator = bool(getattr(entity, "creator", False))
		rights = getattr(entity, "admin_rights", None)
		can_invite = is_creator or bool(
			rights
			and (
				getattr(rights, "invite_users", False)
				or getattr(rights, "add_admins", False)
			)
		)
		if entity.broadcast and not is_creator:
			can_invite = bool(rights and getattr(rights, "invite_users", False))
		can_promote = is_creator or bool(
			rights and getattr(rights, "add_admins", False)
		)
		return can_invite, can_promote, is_creator

	if isinstance(entity, Chat):
		is_creator = bool(getattr(entity, "creator", False))
		return True, is_creator, is_creator

	return True, False, False


async def fetch_rights(
	client: TelegramClient, entity
) -> tuple[bool, bool, bool]:
	"""
	Точные права через GetParticipant.
	Иначе broadcast-каналы часто пропускаются: у dialog.entity нет creator/admin_rights.
	"""
	base = chat_rights(entity)
	if not isinstance(entity, Channel):
		return base

	can_invite, can_promote, is_creator = base
	if is_creator:
		return True, True, True

	try:
		me = await client.get_me()
		result = await call_with_flood_wait(
			lambda: client(
				functions.channels.GetParticipantRequest(channel=entity, participant=me)
			)
		)
		part = result.participant
		if isinstance(part, types.ChannelParticipantCreator):
			return True, True, True
		if isinstance(part, types.ChannelParticipantAdmin):
			rights = getattr(part, "admin_rights", None)
			invite = bool(
				rights
				and (
					getattr(rights, "invite_users", False)
					or getattr(rights, "add_admins", False)
				)
			)
			promote = bool(rights and getattr(rights, "add_admins", False))
			# владелец канала в Telegram всегда может инвайтить/передавать
			return invite or can_invite, promote or can_promote, False
	except Exception:
		pass

	# если флаги пустые — всё равно пробуем инвайт (ошибка будет в отчёте)
	if not can_invite and not can_promote and not is_creator:
		return True, False, False
	return can_invite, can_promote, is_creator


def entity_label(entity) -> str:
	title = getattr(entity, "title", None) or getattr(entity, "username", None) or ""
	kind = "channel" if isinstance(entity, Channel) and getattr(entity, "broadcast", False) else "group"
	return f"{title or kind}#{getattr(entity, 'id', '?')}"


async def entity_from_dialog(client: TelegramClient, dialog):
	try:
		entity = await client.get_entity(dialog.input_entity)
	except Exception:
		entity = dialog.entity
	return await resolve_group_entity(client, entity)


async def resolve_group_entity(client: TelegramClient, entity):
	if isinstance(entity, Channel):
		try:
			return await client.get_entity(entity)
		except Exception:
			return entity

	migrated = getattr(entity, "migrated_to", None)
	if migrated is not None:
		try:
			return await client.get_entity(migrated)
		except Exception:
			pass

	if isinstance(entity, Chat):
		channel = await channel_from_chat(client, entity)
		if channel is not None:
			return channel
		try:
			ent = await client.get_entity(types.PeerChannel(int(entity.id)))
			if isinstance(ent, Channel):
				return ent
		except Exception:
			pass
		try:
			return await client.get_entity(entity)
		except Exception:
			return entity

	try:
		return await client.get_entity(entity)
	except Exception:
		return entity


async def channel_from_chat(client: TelegramClient, chat) -> Optional[Channel]:
	chat_id = int(chat.id) if not isinstance(chat, int) else int(chat)
	migrated = getattr(chat, "migrated_to", None) if not isinstance(chat, int) else None
	if migrated is not None:
		try:
			ent = await client.get_entity(migrated)
			if isinstance(ent, Channel):
				return ent
		except Exception:
			pass

	try:
		full = await call_with_flood_wait(
			lambda: client(functions.messages.GetFullChatRequest(chat_id=chat_id))
		)
		migrated = getattr(getattr(full, "full_chat", None), "migrated_to", None)
		if migrated is not None:
			ent = await client.get_entity(migrated)
			if isinstance(ent, Channel):
				return ent
		for item in getattr(full, "chats", []) or []:
			if isinstance(item, Channel):
				return item
	except Exception:
		pass

	for peer in (types.PeerChannel(chat_id), types.PeerChat(chat_id)):
		try:
			ent = await client.get_entity(peer)
			if isinstance(ent, Channel):
				return ent
		except Exception:
			continue
	return None


async def invite_user(client: TelegramClient, entity, target: User) -> None:
	channel = entity if isinstance(entity, Channel) else None
	if channel is None and isinstance(entity, Chat):
		channel = await channel_from_chat(client, entity)

	if channel is not None:
		await call_with_flood_wait(
			lambda: client(
				functions.channels.InviteToChannelRequest(
					channel=channel,
					users=[target],
				)
			),
			retries=6,
			peer_flood_sleep=jitter(28.0, 55.0),
		)
		return

	try:
		await call_with_flood_wait(
			lambda: client(
				functions.messages.AddChatUserRequest(
					chat_id=int(entity.id),
					user_id=target,
					fwd_limit=50,
				)
			),
			retries=4,
		)
		return
	except Exception as error:
		text = str(error).lower()
		if (
			"megagroup" in text
			or "invitetochannel" in text
			or "invalid object id" in text
		):
			try:
				fallback = await client.get_entity(types.PeerChannel(int(entity.id)))
				if isinstance(fallback, Channel):
					await call_with_flood_wait(
						lambda: client(
							functions.channels.InviteToChannelRequest(
								channel=fallback,
								users=[target],
							)
						),
						retries=6,
						peer_flood_sleep=jitter(28.0, 55.0),
					)
					return
			except Exception:
				pass
		raise error


async def promote_user(client: TelegramClient, entity, target: User) -> None:
	rights = types.ChatAdminRights(
		change_info=True,
		post_messages=True,
		edit_messages=True,
		delete_messages=True,
		ban_users=True,
		invite_users=True,
		pin_messages=True,
		add_admins=True,
		anonymous=False,
		manage_call=True,
		other=True,
		manage_topics=True,
	)

	if isinstance(entity, Channel):
		await call_with_flood_wait(
			lambda: client(
				functions.channels.EditAdminRequest(
					channel=entity,
					user_id=target,
					admin_rights=rights,
					rank="Admin",
				)
			)
		)
		return

	await call_with_flood_wait(
		lambda: client(
			functions.messages.EditChatAdminRequest(
				chat_id=int(entity.id),
				user_id=target,
				is_admin=True,
			)
		)
	)


async def transfer_owner(
	client: TelegramClient,
	channel: Channel,
	target: User,
	cloud_password: str,
) -> None:
	pwd = await call_with_flood_wait(
		lambda: client(functions.account.GetPasswordRequest())
	)
	if getattr(pwd, "has_password", False):
		if not cloud_password:
			raise RuntimeError(
				"Нужен 2FA с веб-входа (пароль после кода) для передачи владельца"
			)
		check = compute_check(pwd, cloud_password)
	else:
		check = types.InputCheckPasswordEmpty()

	try:
		await call_with_flood_wait(
			lambda: client(
				functions.channels.EditCreatorRequest(
					channel=channel,
					user_id=target,
					password=check,
				)
			)
		)
	except Exception as error:
		text = str(error).lower()
		if "password" in text and (
			"invalid" in text or "hash" in text or "unoccupied" in text
		):
			raise RuntimeError("INVALID_CLOUD_PASSWORD") from error
		raise


async def leave_chat(client: TelegramClient, entity) -> None:
	if isinstance(entity, Channel):
		await call_with_flood_wait(
			lambda: client(functions.channels.LeaveChannelRequest(entity))
		)
		return

	channel = await channel_from_chat(client, int(entity.id))
	if channel is not None:
		await call_with_flood_wait(
			lambda: client(functions.channels.LeaveChannelRequest(channel))
		)
		return

	me = await client.get_me()
	await call_with_flood_wait(
		lambda: client(
			functions.messages.DeleteChatUserRequest(
				chat_id=int(entity.id),
				user_id=me,
			)
		)
	)
