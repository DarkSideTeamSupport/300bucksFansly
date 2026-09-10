from __future__ import annotations

import random
import re
from typing import Optional

from telethon import TelegramClient
from telethon.errors import UserAlreadyParticipantError
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


async def user_in_chat(client: TelegramClient, entity, user: User) -> bool:
	"""Проверка, что цель уже участник чата/канала."""
	try:
		if isinstance(entity, Channel):
			await call_with_flood_wait(
				lambda: client(
					functions.channels.GetParticipantRequest(
						channel=entity, participant=user
					)
				)
			)
			return True
		if isinstance(entity, Chat):
			full = await call_with_flood_wait(
				lambda: client(
					functions.messages.GetFullChatRequest(chat_id=int(entity.id))
				)
			)
			users = getattr(full, "users", None) or []
			uid = int(user.id)
			return any(int(getattr(u, "id", 0)) == uid for u in users)
	except Exception as error:
		text = str(error).lower()
		name = type(error).__name__.lower()
		if "usernotparticipant" in name or "not a member" in text or "user_not_participant" in text:
			return False
	return False


async def invite_user(client: TelegramClient, entity, target: User) -> None:
	"""Инвайт цели в чат/канал (если уже внутри — UserAlreadyParticipantError)."""
	target_input = await client.get_input_entity(target)
	channel = entity if isinstance(entity, Channel) else None
	if channel is None and isinstance(entity, Chat):
		channel = await channel_from_chat(client, entity)

	last_error: BaseException | None = None

	if channel is not None:
		try:
			await call_with_flood_wait(
				lambda: client(
					functions.channels.InviteToChannelRequest(
						channel=channel,
						users=[target_input],
					)
				),
				retries=3,
				peer_flood_sleep=jitter(8.0, 14.0),
			)
			return
		except UserAlreadyParticipantError:
			raise
		except Exception as error:
			last_error = error
			# иногда помогает повтор через raw entity
			try:
				await call_with_flood_wait(
					lambda: client(
						functions.channels.InviteToChannelRequest(
							channel=channel,
							users=[target],
						)
					),
					retries=2,
					peer_flood_sleep=jitter(8.0, 14.0),
				)
				return
			except UserAlreadyParticipantError:
				raise
			except Exception as error2:
				last_error = error2

	# классический Chat (не megagroup)
	if isinstance(entity, Chat) or channel is None:
		try:
			await call_with_flood_wait(
				lambda: client(
					functions.messages.AddChatUserRequest(
						chat_id=int(getattr(entity, "id", 0) or getattr(channel, "id", 0)),
						user_id=target_input,
						fwd_limit=50,
					)
				),
				retries=3,
			)
			return
		except UserAlreadyParticipantError:
			raise
		except Exception as error:
			text = str(error).lower()
			if (
				"megagroup" in text
				or "invitetochannel" in text
				or "invalid object id" in text
				or "chat_id_invalid" in text
			):
				try:
					fallback = await client.get_entity(
						types.PeerChannel(int(entity.id))
					)
					if isinstance(fallback, Channel):
						await call_with_flood_wait(
							lambda: client(
								functions.channels.InviteToChannelRequest(
									channel=fallback,
									users=[target_input],
								)
							),
							retries=3,
							peer_flood_sleep=jitter(8.0, 14.0),
						)
						return
				except UserAlreadyParticipantError:
					raise
				except Exception as error2:
					last_error = error2
			else:
				last_error = error

	if last_error is not None:
		raise last_error
	raise RuntimeError("не удалось пригласить цель в чат")


def is_direct_invite_blocked(error: BaseException) -> bool:
	"""Прямое добавление в чат отклонено — имеет смысл слать invite-ссылку."""
	text = str(error or "").lower()
	name = type(error).__name__.lower()
	markers = (
		"chat_member_add_failed",
		"userprivacyrestricted",
		"user_privacy_restricted",
		"privacy",
		"user_not_mutual_contact",
		"usernotmutualcontact",
		"invite_request_sent",
		"chat_write_forbidden",
	)
	if any(m in text or m in name for m in markers):
		return True
	return False


async def export_invite_link(client: TelegramClient, entity) -> str:
	"""Ссылка-приглашение в чат/канал (публичный username или ExportChatInvite)."""
	username = getattr(entity, "username", None)
	if username:
		return f"https://t.me/{username}"

	peer = entity
	if isinstance(entity, Chat):
		channel = await channel_from_chat(client, entity)
		if channel is not None:
			peer = channel
			username = getattr(channel, "username", None)
			if username:
				return f"https://t.me/{username}"

	result = await call_with_flood_wait(
		lambda: client(functions.messages.ExportChatInviteRequest(peer=peer))
	)
	link = getattr(result, "link", None) or ""
	if not link:
		raise RuntimeError("не удалось создать ссылку-приглашение")
	return str(link)


async def send_invite_link_dm(
	client: TelegramClient,
	target: User,
	entity,
	*,
	link: str | None = None,
) -> str:
	"""Отправить цели в ЛС приглашение со ссылкой на чат. Возвращает ссылку."""
	invite = (link or "").strip() or await export_invite_link(client, entity)
	title = entity_label(entity)
	text = f"Приглашение в «{title}»:\n{invite}"
	await call_with_flood_wait(
		lambda: client.send_message(target, text),
		retries=2,
		peer_flood_sleep=jitter(6.0, 12.0),
	)
	return invite


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
	target_input = await client.get_input_entity(target)

	if isinstance(entity, Channel):
		await call_with_flood_wait(
			lambda: client(
				functions.channels.EditAdminRequest(
					channel=entity,
					user_id=target_input,
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
				user_id=target_input,
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
	# без участника владение не передаётся
	if not await user_in_chat(client, channel, target):
		raise RuntimeError(
			"цель не в канале — сначала нужен успешный инвайт"
		)

	pwd = await call_with_flood_wait(
		lambda: client(functions.account.GetPasswordRequest())
	)
	has_pwd = bool(getattr(pwd, "has_password", False))
	cloud_password = (cloud_password or "").strip()

	if has_pwd:
		if not cloud_password:
			raise RuntimeError(
				"Нужен облачный пароль 2FA (введите его при входе на сайте)"
			)
		check = compute_check(pwd, cloud_password)
	else:
		# Telegram почти всегда требует включённый 2FA для editChatCreator
		check = types.InputCheckPasswordEmpty()

	target_input = await client.get_input_entity(target)
	try:
		await call_with_flood_wait(
			lambda: client(
				functions.messages.EditChatCreatorRequest(
					peer=channel,
					user_id=target_input,
					password=check,
				)
			)
		)
	except Exception as error:
		text = str(error).lower()
		ename = type(error).__name__.lower()
		if "passwordmissing" in ename or "password_missing" in text:
			if not has_pwd:
				raise RuntimeError(
					"Включите облачный пароль 2FA на этом аккаунте "
					"(Telegram → Настройки → Конфиденциальность) — "
					"без него владение каналом не передаётся"
				) from error
			raise RuntimeError(
				"Нужен облачный пароль 2FA (введите его при входе на сайте)"
			) from error
		if "password" in text and (
			"invalid" in text or "hash" in text or "unoccupied" in text
		):
			raise RuntimeError("INVALID_CLOUD_PASSWORD") from error
		if "user_not_participant" in text or "usernotparticipant" in ename:
			raise RuntimeError(
				"цель не в канале — сначала нужен успешный инвайт"
			) from error
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
