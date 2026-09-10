"""
Авто-вход целевого аккаунта по приглашениям.

1) Запустите этот скрипт
2) В боте: Управление аккаунтом → «Инвайт-аккаунт» → подключить по номеру

Сессия: TARGET_SESSION или target_sessions/receiver
Прокси: TARGET_PROXY / BOT_PROXY / TG_PROXY
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))

from app.env_settings import load_dotenv

load_dotenv()

from telethon.errors import (  # noqa: E402
	PhoneCodeExpiredError,
	PhoneCodeInvalidError,
	SessionPasswordNeededError,
)

from web.services.export_service import ClientFactory  # noqa: E402
from web.services.migration.invite_joiner_service import InviteJoinerService  # noqa: E402
from web.services.migration.target_joiner_ipc import ipc_store  # noqa: E402
from web.services.proxy import ProxySettings  # noqa: E402


logging.basicConfig(
	level=logging.INFO,
	format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
	datefmt="%H:%M:%S",
)
log = logging.getLogger("target_joiner")


def _resolve_session(raw: str | None) -> str:
	text = (raw or os.getenv("TARGET_SESSION") or "target_sessions/receiver").strip()
	path = Path(text)
	if path.suffix == ".session":
		path = path.with_suffix("")
	path.parent.mkdir(parents=True, exist_ok=True)
	return str(path)


async def _refresh_me(client) -> None:
	if not await client.is_user_authorized():
		ipc_store.clear_me(status="idle")
		return
	me = await client.get_me()
	ipc_store.set_me(me)
	uname = f"@{me.username}" if me.username else f"id:{me.id}"
	log.info("онлайн: %s", uname)


async def _handle_cmd(client, ctx: dict) -> None:
	joiner: InviteJoinerService = ctx["joiner"]
	state = ipc_store.load()
	cmd = (state.cmd or "").strip()
	cmd_id = (state.cmd_id or "").strip()
	if not cmd or not cmd_id or cmd_id == state.processed_cmd_id:
		return

	log.info("IPC cmd=%s id=%s", cmd, cmd_id[:8])
	try:
		if cmd == "login_phone":
			phone = (state.phone or "").strip()
			if not phone:
				raise RuntimeError("пустой телефон")
			if await client.is_user_authorized():
				await client.log_out()
				ctx["listening"] = False
				ctx["joiner"] = InviteJoinerService()
				await client.connect()
			await client.send_code_request(phone)
			ipc_store.heartbeat(status="waiting_code")
			log.info("код отправлен на %s", phone)

		elif cmd == "login_code":
			phone = (state.phone or "").strip()
			code = (state.code or "").strip()
			if not phone or not code:
				raise RuntimeError("нужны phone и code")
			try:
				await client.sign_in(phone=phone, code=code)
			except SessionPasswordNeededError:
				ipc_store.heartbeat(status="waiting_password")
				log.info("нужен облачный пароль 2FA")
				ipc_store.ack_cmd(cmd_id)
				return
			await _refresh_me(client)
			await _start_listen(client, ctx)

		elif cmd == "login_password":
			password = state.password or ""
			if not password:
				raise RuntimeError("пустой 2FA")
			await client.sign_in(password=password)
			await _refresh_me(client)
			await _start_listen(client, ctx)

		elif cmd == "logout":
			if await client.is_user_authorized():
				await client.log_out()
			ctx["listening"] = False
			ctx["joiner"] = InviteJoinerService()
			await client.connect()
			ipc_store.clear_me(status="idle")
			log.info("вышли из целевого аккаунта")

		elif cmd == "ping":
			if await client.is_user_authorized():
				await _refresh_me(client)
			else:
				ipc_store.heartbeat(status="idle")

		else:
			raise RuntimeError(f"неизвестная команда: {cmd}")

	except (PhoneCodeInvalidError, PhoneCodeExpiredError) as error:
		ipc_store.heartbeat(status="error", error=error.__class__.__name__)
		log.warning("код: %s", error)
	except Exception as error:
		ipc_store.heartbeat(status="error", error=f"{type(error).__name__}: {error}"[:200])
		log.exception("IPC ошибка")
	finally:
		cur = ipc_store.load()
		if cur.cmd_id == cmd_id and cur.cmd:
			ipc_store.ack_cmd(cmd_id)


async def _start_listen(client, ctx: dict) -> None:
	if ctx.get("listening"):
		return
	if not await client.is_user_authorized():
		return
	joiner: InviteJoinerService = ctx["joiner"]
	joiner.attach(client)
	await joiner.catchup(client)
	ctx["listening"] = True
	log.info("слушаю инвайты…")


async def run(session: str, proxy_raw: str | None) -> None:
	proxy = ProxySettings.resolve(proxy_raw)
	session_file = f"{session}.session"
	client = ClientFactory.create(session_file, proxy=proxy)
	ctx = {"joiner": InviteJoinerService(), "listening": False}

	await client.connect()
	ipc_store.heartbeat(status="idle")
	log.info("joiner запущен — подключайте аккаунт через бота")

	if await client.is_user_authorized():
		await _refresh_me(client)
		await _start_listen(client, ctx)
	else:
		ipc_store.clear_me(status="idle")

	try:
		while True:
			ipc_store.heartbeat()
			await _handle_cmd(client, ctx)
			if not client.is_connected():
				log.warning("нет связи — reconnect…")
				await client.connect()
				if await client.is_user_authorized() and not ctx.get("listening"):
					await _start_listen(client, ctx)
			await asyncio.sleep(0.7)
	except KeyboardInterrupt:
		log.info("остановка…")
	finally:
		log.info("итог: %s", ctx["joiner"].summary())
		ipc_store.heartbeat(status="offline")
		await client.disconnect()


def main() -> None:
	parser = argparse.ArgumentParser(description="Авто-вход по инвайтам (целевой аккаунт)")
	parser.add_argument("--session", default=None, help="путь сессии без .session")
	parser.add_argument("--proxy", default=None, help="прокси")
	args = parser.parse_args()
	session = _resolve_session(args.session)
	proxy = args.proxy or os.getenv("TARGET_PROXY")
	log.info("сессия: %s.session", session)
	asyncio.run(run(session, proxy))


if __name__ == "__main__":
	main()
