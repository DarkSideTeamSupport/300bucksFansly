from __future__ import annotations

from urllib import error, parse, request


def send_telegram_text(token: str, chat_id: str, text: str) -> None:
	url = f"https://api.telegram.org/bot{token}/sendMessage"
	payload = parse.urlencode(
		{
			"chat_id": chat_id,
			"text": text[:3500],
			"disable_web_page_preview": "1",
		}
	).encode("utf-8")
	req = request.Request(url, data=payload, method="POST")
	try:
		with request.urlopen(req, timeout=30) as resp:
			resp.read()
	except error.HTTPError as exc:
		body = ""
		try:
			body = exc.read().decode("utf-8", errors="replace")[:500]
		except Exception:
			pass
		raise RuntimeError(f"HTTP {exc.code}: {body or exc.reason}") from exc
