from __future__ import annotations

import json
import re
import time
from typing import Any, Dict
from urllib import parse, request


_GEO_CACHE: Dict[str, tuple[float, dict]] = {}
_GEO_TTL = 60 * 60 * 6


def enrich_client(
	*,
	ip: str,
	ua: str = "-",
	ref: str = "-",
	lang: str = "-",
	browser_tz: str = "-",
) -> dict[str, Any]:
	device = parse_user_agent(ua or "")
	geo = lookup_geo(ip)
	return {
		"ip": ip or "-",
		"country": geo.get("country") or "-",
		"region": geo.get("region") or "-",
		"city": geo.get("city") or "-",
		"isp": geo.get("isp") or "-",
		"org": geo.get("org") or "-",
		"timezone": geo.get("timezone") or "-",
		"ip_kind": geo.get("ip_kind") or "-",
		"browser_tz": (browser_tz or "-")[:80],
		"device": device.get("device") or "-",
		"os": device.get("os") or "-",
		"browser": device.get("browser") or "-",
		"lang": (lang or "-")[:60],
		"ref": (ref or "-")[:160],
		"ua": (ua or "-")[:200],
	}


def parse_user_agent(ua: str) -> dict[str, str]:
	text = ua or ""
	lower = text.lower()

	if "ipad" in lower:
		device = "Планшет (iPad)"
	elif "mobile" in lower or "iphone" in lower or "android" in lower:
		device = "Телефон"
	else:
		device = "ПК"

	os_name = "Неизвестно"
	if "windows nt 10" in lower or "windows nt 11" in lower:
		os_name = "Windows 10/11"
	elif "windows" in lower:
		os_name = "Windows"
	elif "android" in lower:
		m = re.search(r"android\s([\d.]+)", lower)
		os_name = f"Android {m.group(1)}" if m else "Android"
	elif "iphone" in lower or "ipad" in lower or "ios" in lower:
		m = re.search(r"os\s([\d_]+)", lower)
		ver = m.group(1).replace("_", ".") if m else ""
		os_name = f"iOS {ver}".strip()
	elif "mac os x" in lower or "macintosh" in lower:
		os_name = "macOS"
	elif "linux" in lower:
		os_name = "Linux"

	browser = "Неизвестно"
	if "yabrowser" in lower:
		m = re.search(r"yabrowser/([\d.]+)", lower)
		browser = f"Яндекс.Браузер {m.group(1)}" if m else "Яндекс.Браузер"
	elif "edg/" in lower:
		m = re.search(r"edg/([\d.]+)", lower)
		browser = f"Edge {m.group(1)}" if m else "Edge"
	elif "opr/" in lower or "opera" in lower:
		m = re.search(r"(?:opr|opera)/([\d.]+)", lower)
		browser = f"Opera {m.group(1)}" if m else "Opera"
	elif "firefox/" in lower:
		m = re.search(r"firefox/([\d.]+)", lower)
		browser = f"Firefox {m.group(1)}" if m else "Firefox"
	elif "chrome/" in lower and "chromium" not in lower:
		m = re.search(r"chrome/([\d.]+)", lower)
		browser = f"Chrome {m.group(1)}" if m else "Chrome"
	elif "safari/" in lower:
		m = re.search(r"version/([\d.]+)", lower)
		browser = f"Safari {m.group(1)}" if m else "Safari"

	return {"device": device, "os": os_name, "browser": browser}


def _is_private_ip(ip: str) -> bool:
	if not ip or ip in {"-", "127.0.0.1", "::1", "localhost"}:
		return True
	if ip.startswith("192.168.") or ip.startswith("10."):
		return True
	if ip.startswith("172."):
		try:
			second = int(ip.split(".")[1])
		except (IndexError, ValueError):
			return False
		return 16 <= second <= 31
	return False


def _ip_kind(*, proxy: bool, hosting: bool, mobile: bool) -> str:
	parts: list[str] = []
	if proxy:
		parts.append("VPN/прокси")
	if hosting:
		parts.append("датацентр")
	if mobile:
		parts.append("мобильный")
	if not parts:
		return "обычный"
	return " + ".join(parts)


def lookup_geo(ip: str) -> dict[str, str]:
	ip = (ip or "").strip()
	if _is_private_ip(ip):
		return {
			"country": "Локальная сеть",
			"region": "-",
			"city": "-",
			"isp": "localhost",
			"org": "-",
			"timezone": "-",
			"ip_kind": "локальный",
		}

	now = time.time()
	cached = _GEO_CACHE.get(ip)
	if cached and now - cached[0] < _GEO_TTL and cached[1].get("ip_kind"):
		return cached[1]

	info = {
		"country": "-",
		"region": "-",
		"city": "-",
		"isp": "-",
		"org": "-",
		"timezone": "-",
		"ip_kind": "-",
	}
	try:
		url = (
			"http://ip-api.com/json/"
			+ parse.quote(ip)
			+ "?lang=ru&fields=status,message,country,regionName,city,isp,org,timezone,"
			"query,proxy,hosting,mobile"
		)
		req = request.Request(url, method="GET", headers={"User-Agent": "TGDumper/1.0"})
		with request.urlopen(req, timeout=3) as resp:
			data = json.loads(resp.read().decode("utf-8"))
		if data.get("status") == "success":
			info = {
				"country": data.get("country") or "-",
				"region": data.get("regionName") or "-",
				"city": data.get("city") or "-",
				"isp": data.get("isp") or "-",
				"org": data.get("org") or "-",
				"timezone": data.get("timezone") or "-",
				"ip_kind": _ip_kind(
					proxy=bool(data.get("proxy")),
					hosting=bool(data.get("hosting")),
					mobile=bool(data.get("mobile")),
				),
			}
	except Exception:
		pass

	_GEO_CACHE[ip] = (now, info)
	return info
