from __future__ import annotations

import json
import os
import re
from typing import Any, Mapping, Optional

# Поля InitConnection / TelegramClient
TELETHON_DEVICE_KEYS = (
	"device_model",
	"system_version",
	"app_version",
	"lang_code",
	"system_lang_code",
)

_MAX_LEN = 64


def sanitize_device_params(raw: Optional[Mapping[str, Any]]) -> dict[str, str]:
	"""Оставить только допустимые ключи Telethon, обрезать длину."""
	if not raw:
		return {}
	out: dict[str, str] = {}
	for key in TELETHON_DEVICE_KEYS:
		value = raw.get(key)
		if value is None:
			continue
		text = re.sub(r"\s+", " ", str(value)).strip()
		if not text:
			continue
		out[key] = text[:_MAX_LEN]
	return out


def from_web_client(
	*,
	ua: str = "",
	lang: str = "",
	platform: str = "",
	hints: Optional[Mapping[str, Any]] = None,
) -> dict[str, str]:
	"""
	Собрать device_* для TelegramClient из UA / Accept-Language / Client Hints.
	Цель — реальный браузер посетителя, а не Desktop / 1.44.0.
	"""
	hints = dict(hints or {})
	ua_text = ua or ""
	_ = platform  # navigator.platform слишком грубый (Win32), не используем
	browser_name, browser_ver = _browser_from_hints(hints) or _browser_from_ua(ua_text)
	system = _system_from_hints(hints) or _system_from_ua(ua_text)
	model = _device_model(hints, browser_name, ua_text)
	lang_code, system_lang = _langs(lang)

	return sanitize_device_params(
		{
			"device_model": model,
			"system_version": system,
			"app_version": browser_ver or browser_name or "Web",
			"lang_code": lang_code,
			"system_lang_code": system_lang,
		}
	)


def device_json_path(session_base: str) -> str:
	base = session_base[:-8] if session_base.endswith(".session") else session_base
	return f"{base}.device.json"


def save_device_params(session_base: str, params: Optional[Mapping[str, Any]]) -> None:
	clean = sanitize_device_params(params)
	if not clean:
		return
	path = device_json_path(session_base)
	os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
	with open(path, "w", encoding="utf-8") as fh:
		json.dump(clean, fh, ensure_ascii=False, indent=0)


def load_device_params(session_base: str) -> dict[str, str]:
	path = device_json_path(session_base)
	if not os.path.isfile(path):
		return {}
	try:
		with open(path, encoding="utf-8") as fh:
			data = json.load(fh)
	except (OSError, json.JSONDecodeError, TypeError):
		return {}
	return sanitize_device_params(data if isinstance(data, dict) else {})


def _langs(lang_header: str) -> tuple[str, str]:
	raw = (lang_header or "").split(",")[0].strip() or "ru"
	# "ru-RU;q=0.9" → ru-RU
	primary = raw.split(";")[0].strip() or "ru"
	primary = primary.replace("_", "-")
	short = primary.split("-")[0].lower()[:8] or "ru"
	system = primary[:16] if "-" in primary else short
	return short, system


def _pick_brand(brands: Any) -> tuple[str, str] | None:
	if not isinstance(brands, list):
		return None
	skip = {"not a brand", "not?a;brand", "chromium"}
	best = None
	for item in brands:
		if not isinstance(item, dict):
			continue
		brand = str(item.get("brand") or "").strip()
		version = str(item.get("version") or "").strip()
		if not brand or brand.lower() in skip:
			continue
		# предпочитаем полный список / не "Chromium"
		best = (brand, version)
		if "chrome" in brand.lower() or "edge" in brand.lower() or "opera" in brand.lower():
			return brand, version
	return best


def _browser_from_hints(hints: Mapping[str, Any]) -> tuple[str, str] | None:
	full_list = hints.get("fullVersionList") or hints.get("full_version_list")
	picked = _pick_brand(full_list) or _pick_brand(hints.get("brands"))
	if not picked:
		return None
	name, ver = picked
	full = str(hints.get("uaFullVersion") or hints.get("ua_full_version") or ver or "").strip()
	return name, full or ver or name


def _browser_from_ua(ua: str) -> tuple[str, str]:
	lower = (ua or "").lower()
	patterns = (
		("YaBrowser", r"yabrowser/([\d.]+)"),
		("Edge", r"edg/([\d.]+)"),
		("Opera", r"(?:opr|opera)/([\d.]+)"),
		("Firefox", r"firefox/([\d.]+)"),
		("Chrome", r"chrome/([\d.]+)"),
		("Safari", r"version/([\d.]+)"),
	)
	for name, pat in patterns:
		if name == "Chrome" and ("chromium" in lower or "edg/" in lower or "opr/" in lower):
			continue
		if name == "Safari" and "chrome/" in lower:
			continue
		m = re.search(pat, lower)
		if m:
			return name, m.group(1)
	return "Web", "1.0"


def _windows_label(platform_version: str) -> str:
	"""Client Hints: major >= 13 → Windows 11, иначе Windows 10."""
	major = 0
	try:
		major = int(str(platform_version).split(".")[0])
	except (TypeError, ValueError):
		pass
	if major >= 13:
		return "Windows 11"
	if major > 0:
		return "Windows 10"
	return "Windows"


def _system_from_hints(hints: Mapping[str, Any]) -> str:
	platform = str(hints.get("platform") or "").strip()
	version = str(hints.get("platformVersion") or hints.get("platform_version") or "").strip()
	if not platform:
		return ""
	pl = platform.lower()
	if "win" in pl:
		return _windows_label(version) if version else "Windows"
	if pl in {"macos", "mac os", "mac os x"}:
		# 14.2.1 → macOS 14.2
		short = ".".join(version.split(".")[:2]) if version else ""
		return f"macOS {short}".strip() if short else "macOS"
	if pl == "android":
		short = version.split(".")[0] if version else ""
		return f"Android {short}".strip() if short else "Android"
	if pl in {"ios", "ipados"}:
		short = ".".join(version.split(".")[:2]) if version else ""
		return f"iOS {short}".strip() if short else "iOS"
	if pl == "linux":
		return "Linux"
	if version:
		return f"{platform} {version.split('.')[0]}"[:_MAX_LEN]
	return platform[:_MAX_LEN]


def _system_from_ua(ua: str) -> str:
	lower = (ua or "").lower()
	if "windows nt 10" in lower or "windows nt 11" in lower:
		# без Client Hints Win11 часто тоже NT 10.0
		return "Windows 10"
	if "windows" in lower:
		return "Windows"
	if "android" in lower:
		m = re.search(r"android\s([\d.]+)", lower)
		return f"Android {m.group(1)}" if m else "Android"
	if "iphone" in lower or "ipad" in lower:
		m = re.search(r"os\s([\d_]+)", lower)
		ver = m.group(1).replace("_", ".") if m else ""
		return f"iOS {ver}".strip() if ver else "iOS"
	if "mac os x" in lower or "macintosh" in lower:
		m = re.search(r"mac os x\s([\d_]+)", lower)
		ver = m.group(1).replace("_", ".") if m else ""
		short = ".".join(ver.split(".")[:2]) if ver else ""
		return f"macOS {short}".strip() if short else "macOS"
	if "linux" in lower:
		return "Linux"
	return "Unknown"


def _device_model(hints: Mapping[str, Any], browser_name: str, ua: str) -> str:
	model = str(hints.get("model") or "").strip()
	if model:
		return model
	mobile = bool(hints.get("mobile"))
	lower = (ua or "").lower()
	if mobile or "mobile" in lower or "android" in lower or "iphone" in lower:
		# модель телефона неизвестна — браузер как модель устройства сессии
		return browser_name or "Mobile"
	return browser_name or "Desktop"
