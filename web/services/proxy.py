from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import unquote, urlparse


@dataclass(frozen=True)
class ProxySettings:
	"""Резидентский/любой прокси для Telethon: socks5://user:pass@host:port"""

	proxy_type: str
	addr: str
	port: int
	username: Optional[str] = None
	password: Optional[str] = None
	rdns: bool = True

	def to_telethon(self) -> Dict[str, Any]:
		data: Dict[str, Any] = {
			"proxy_type": self.proxy_type,
			"addr": self.addr,
			"port": self.port,
			"rdns": self.rdns,
		}
		if self.username:
			data["username"] = self.username
		if self.password:
			data["password"] = self.password
		return data

	@staticmethod
	def parse(raw: Optional[str]) -> Optional["ProxySettings"]:
		text = (raw or "").strip()
		if not text:
			return None

		if "://" not in text:
			# host:port или user:pass@host:port → socks5 по умолчанию
			text = f"socks5://{text}"

		parsed = urlparse(text)
		scheme = (parsed.scheme or "").lower()
		if scheme in ("socks5h",):
			scheme = "socks5"
		if scheme not in ("socks5", "socks4", "http"):
			raise ValueError("Поддерживаются socks5 / socks4 / http")

		if not parsed.hostname or not parsed.port:
			raise ValueError("Укажите host и port прокси")

		return ProxySettings(
			proxy_type=scheme,
			addr=parsed.hostname,
			port=int(parsed.port),
			username=unquote(parsed.username) if parsed.username else None,
			password=unquote(parsed.password) if parsed.password else None,
			rdns=True,
		)
