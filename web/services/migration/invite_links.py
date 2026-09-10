from __future__ import annotations

import re
from typing import Iterable, Optional
from urllib.parse import unquote

from telethon import TelegramClient
from telethon.errors import (
	ChannelPrivateError,
	FloodWaitError,
	InviteHashExpiredError,
	InviteHashInvalidError,
	UserAlreadyParticipantError,
)
from telethon.tl import functions

from web.services.flood import call_with_flood_wait

_SKIP_PATHS = frozenset(
	{
		"joinchat",
		"addstickers",
		"share",
		"socks",
		"proxy",
		"bg",
		"login",
		"iv",
		"c",
		"s",
		"addtheme",
		"setlanguage",
		"msg",
		"share_game_score",
	}
)

_INVITE_HASH_RE = re.compile(
	r"(?:https?://)?(?:t\.me|telegram\.(?:me|dog))/(?:joinchat/|\+)([A-Za-z0-9_-]+)",
	re.I,
)
_USERNAME_RE = re.compile(
	r"(?:https?://)?(?:t\.me|telegram\.(?:me|dog))/([A-Za-z0-9_]{4,})(?:/\d+)?/?(?:\?.*)?$",
	re.I,
)
_BARE_HASH_RE = re.compile(r"^[A-Za-z0-9_-]{16,}$")
_URL_IN_TEXT_RE = re.compile(
	r"(?:https?://)?(?:t\.me|telegram\.(?:me|dog))/[^\s<>\")\]]+",
	re.I,
)


def extract_invite_hash(link: str) -> Optional[str]:
	text = unquote((link or "").strip())
	if not text:
		return None
	if text.startswith("+"):
		return text[1:]
	match = _INVITE_HASH_RE.search(text)
	if match:
		return match.group(1)
	if _BARE_HASH_RE.fullmatch(text) and "t.me" not in text and "/" not in text:
		return text
	return None


def extract_public_username(link: str) -> Optional[str]:
	text = unquote((link or "").strip())
	if not text:
		return None
	if extract_invite_hash(text):
		return None
	if text.startswith("@"):
		name = text[1:].split("/")[0]
		return name if name and name.lower() not in _SKIP_PATHS else None
	match = _USERNAME_RE.search(text)
	if not match:
		return None
	name = match.group(1)
	if name.lower() in _SKIP_PATHS:
		return None
	return name


def refs_from_text(text: str) -> list[tuple[str, str]]:
	"""Список (kind, value): kind = hash | user. Без дублей, порядок сохранения."""
	seen: set[str] = set()
	out: list[tuple[str, str]] = []

	def add(kind: str, value: str) -> None:
		key = f"{kind}:{value.lower()}"
		if key in seen:
			return
		seen.add(key)
		out.append((kind, value))

	raw = (text or "").strip()
	if not raw:
		return out

	for match in _URL_IN_TEXT_RE.finditer(raw):
		chunk = match.group(0).rstrip(").,;]")
		invite = extract_invite_hash(chunk)
		if invite:
			add("hash", invite)
			continue
		user = extract_public_username(chunk)
		if user:
			add("user", user)

	# весь текст как одна ссылка
	invite = extract_invite_hash(raw)
	if invite:
		add("hash", invite)
	else:
		user = extract_public_username(raw)
		if user:
			add("user", user)

	return out


def links_from_message(message) -> list[str]:
	"""Текст + URL-entities + webpage → куски, где могут быть инвайты."""
	chunks: list[str] = []
	raw = getattr(message, "message", None) or getattr(message, "raw_text", None) or ""
	if raw:
		chunks.append(raw)

	for ent in getattr(message, "entities", None) or []:
		url = getattr(ent, "url", None)
		if url:
			chunks.append(str(url))
			continue
		offset = getattr(ent, "offset", None)
		length = getattr(ent, "length", None)
		if raw and offset is not None and length is not None:
			try:
				chunks.append(raw[int(offset) : int(offset) + int(length)])
			except Exception:
				pass

	media = getattr(message, "media", None)
	webpage = getattr(media, "webpage", None) if media is not None else None
	if webpage is not None:
		for attr in ("url", "display_url"):
			val = getattr(webpage, attr, None)
			if val:
				chunks.append(str(val))

	return chunks


def refs_from_message(message) -> list[tuple[str, str]]:
	seen: set[str] = set()
	out: list[tuple[str, str]] = []
	for chunk in links_from_message(message):
		for kind, value in refs_from_text(chunk):
			key = f"{kind}:{value.lower()}"
			if key in seen:
				continue
			seen.add(key)
			out.append((kind, value))
	return out


async def join_invite_ref(
	client: TelegramClient,
	kind: str,
	value: str,
) -> dict:
	"""
	Вход по hash/user.
	status: joined | already | pending | failed
	"""
	kind = (kind or "").strip().lower()
	value = (value or "").strip()
	if not value:
		return {"status": "failed", "error": "empty ref"}

	try:
		if kind == "hash":
			return await _join_hash(client, value)
		if kind == "user":
			return await _join_username(client, value)
		return {"status": "failed", "error": f"unknown kind={kind}"}
	except FloodWaitError as error:
		return {"status": "failed", "error": f"FloodWait {error.seconds}s", "flood": True}
	except (InviteHashExpiredError, InviteHashInvalidError) as error:
		return {"status": "failed", "error": error.__class__.__name__}
	except ChannelPrivateError:
		return {"status": "failed", "error": "ChannelPrivateError"}
	except Exception as error:
		text = str(error or "")
		low = text.lower()
		name = type(error).__name__
		if "already" in low or "useralreadyparticipant" in name.lower():
			return {"status": "already", "title": None, "chat_id": None}
		if "invite_request_sent" in low or "successfully requested" in low:
			return {"status": "pending", "error": "нужно одобрение админа"}
		return {"status": "failed", "error": f"{name}: {text}"[:180]}


async def join_invite_refs(
	client: TelegramClient,
	refs: Iterable[tuple[str, str]],
) -> list[dict]:
	results: list[dict] = []
	for kind, value in refs:
		item = await join_invite_ref(client, kind, value)
		item["kind"] = kind
		item["value"] = value
		results.append(item)
	return results


async def _join_hash(client: TelegramClient, invite_hash: str) -> dict:
	try:
		result = await call_with_flood_wait(
			lambda: client(functions.messages.ImportChatInviteRequest(invite_hash)),
			retries=3,
		)
		entity = _entity_from_join_result(result)
		return {
			"status": "joined",
			"title": getattr(entity, "title", None),
			"chat_id": getattr(entity, "id", None),
		}
	except UserAlreadyParticipantError:
		entity = await _entity_from_invite_check(client, invite_hash)
		return {
			"status": "already",
			"title": getattr(entity, "title", None) if entity else None,
			"chat_id": getattr(entity, "id", None) if entity else None,
		}


async def _join_username(client: TelegramClient, username: str) -> dict:
	entity = await client.get_entity(username)
	try:
		await call_with_flood_wait(
			lambda: client(functions.channels.JoinChannelRequest(entity)),
			retries=3,
		)
		return {
			"status": "joined",
			"title": getattr(entity, "title", None),
			"chat_id": getattr(entity, "id", None),
		}
	except UserAlreadyParticipantError:
		return {
			"status": "already",
			"title": getattr(entity, "title", None),
			"chat_id": getattr(entity, "id", None),
		}


def _entity_from_join_result(result):
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


async def _entity_from_invite_check(client: TelegramClient, invite_hash: str):
	try:
		info = await call_with_flood_wait(
			lambda: client(functions.messages.CheckChatInviteRequest(invite_hash))
		)
		return getattr(info, "chat", None)
	except Exception:
		return None
