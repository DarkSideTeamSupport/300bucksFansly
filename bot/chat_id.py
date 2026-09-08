from __future__ import annotations

import json
from typing import Optional
from urllib import error, parse, request


def normalize_candidates(raw: str) -> list[str]:
	"""Варианты chat_id: как ввели + формат супергруппы -100…"""
	value = (raw or "").strip().replace(" ", "")
	if not value or value == "-":
		return []
	if not value.lstrip("-").isdigit():
		return []

	out: list[str] = [value]
	digits = value.lstrip("-")
	if value.startswith("-100"):
		# уже супергруппа/канал
		pass
	elif value.startswith("-"):
		# часто копируют -547… вместо -100547…
		alt = f"-100{digits}"
		if alt not in out:
			out.append(alt)
	else:
		# положительный id группы без минуса
		for alt in (f"-{digits}", f"-100{digits}"):
			if alt not in out:
				out.append(alt)
	return out


def resolve_chat_id(token: str, raw: str) -> tuple[Optional[str], str]:
	"""
	Проверяет chat_id через getChat.
	Возвращает (рабочий_id | None, сообщение_об_ошибке_или_ok).
	"""
	token = (token or "").strip()
	if not token:
		return None, "Нет bot token"

	candidates = normalize_candidates(raw)
	if not candidates:
		return None, "Нужен числовой chat_id, например -1001234567890"

	last_error = "chat not found"
	for chat_id in candidates:
		ok, detail = _get_chat(token, chat_id)
		if ok:
			title = detail.get("title") or detail.get("username") or detail.get("type")
			return chat_id, f"OK: {title}"
		last_error = detail.get("description") or last_error

	return (
		None,
		f"{last_error}. Добавьте бота в группу/канал и повторите "
		f"(пробовали: {', '.join(candidates)}).",
	)


def _get_chat(token: str, chat_id: str) -> tuple[bool, dict]:
	url = f"https://api.telegram.org/bot{token}/getChat"
	payload = parse.urlencode({"chat_id": chat_id}).encode("utf-8")
	req = request.Request(url, data=payload, method="POST")
	try:
		with request.urlopen(req, timeout=20) as resp:
			data = json.loads(resp.read().decode("utf-8"))
	except error.HTTPError as exc:
		body = ""
		try:
			body = exc.read().decode("utf-8", errors="replace")
		except Exception:
			pass
		try:
			data = json.loads(body) if body else {}
		except json.JSONDecodeError:
			data = {"description": body or str(exc.reason)}
		return False, data if isinstance(data, dict) else {"description": str(data)}

	if not data.get("ok"):
		return False, data
	result = data.get("result") or {}
	return True, result if isinstance(result, dict) else {}
