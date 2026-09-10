from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Optional

from telethon.errors import (
	FloodWaitError,
	PasswordHashInvalidError,
	PhoneCodeExpiredError,
	PhoneCodeInvalidError,
	PhoneNumberInvalidError,
	SessionPasswordNeededError,
)
from telethon.password import compute_check
from telethon.tl import functions
from telethon.utils import parse_phone

from app.device_fingerprint import save_device_params
from web.services.export_options import ExportOptions
from web.services.export_service import ClientFactory
from web.services.login_store import AuthStep, LoginState, login_store
from web.services.migration.cloud_secrets import cloud_secrets
from web.services.proxy import ProxySettings


class WebAuthService:
	SESSIONS_DIR = "sessions"

	def __init__(self) -> None:
		self._phone_locks: dict[str, asyncio.Lock] = {}

	def start(self) -> LoginState:
		os.makedirs(self.SESSIONS_DIR, exist_ok=True)
		self.cleanup_orphan_qr_sessions()
		return login_store.create()

	def _phone_lock(self, phone: str) -> asyncio.Lock:
		lock = self._phone_locks.get(phone)
		if lock is None:
			lock = asyncio.Lock()
			self._phone_locks[phone] = lock
		return lock

	async def submit_phone(
		self,
		login_id: str,
		phone_raw: str,
		proxy_raw: Optional[str] = None,
		options: Optional[ExportOptions] = None,
	) -> LoginState:
		state = self._require(login_id)
		if options:
			state.options = options

		try:
			state.proxy = ProxySettings.resolve(proxy_raw)
		except ValueError as error:
			state.step = AuthStep.ERROR
			state.error = f"Прокси: {error}"
			return state

		phone = parse_phone((phone_raw or "").strip())
		if not phone:
			state.step = AuthStep.ERROR
			state.error = "Некорректный номер телефона"
			return state

		async with self._phone_lock(phone):
			return await self._submit_phone_locked(state, phone)

	async def _submit_phone_locked(self, state: LoginState, phone: str) -> LoginState:
		account_base = os.path.join(self.SESSIONS_DIR, phone)
		# снять прошлый qr_/phone_ temp и по возможности освободить account.session
		await self._abandon_temp_session(state)
		await self._disconnect_session_holders(account_base)
		self._clear_qr(state)
		self._checkpoint_session_file(account_base)

		# если account.session уже авторизован — пробуем его; при lock уходим на temp
		reused = await self._try_reuse_account_session(state, phone, account_base)
		if reused is not None:
			return reused

		# код всегда шлём через отдельный файл phone_{login_id} — без конфликта с lock
		session_base = os.path.join(self.SESSIONS_DIR, f"phone_{state.login_id}")
		self._unlink_session(session_base)
		client = ClientFactory.create(
			session_base, proxy=state.proxy, device=state.device_params
		)
		state.client = client
		state.phone = phone
		state.session_path = f"{session_base}.session"
		save_device_params(session_base, state.device_params)

		try:
			await client.connect()
			sent = await client.send_code_request(phone)
			state.phone_code_hash = sent.phone_code_hash
			state.step = AuthStep.CODE
			state.error = None
			return state
		except FloodWaitError as error:
			state.step = AuthStep.ERROR
			state.error = f"FloodWait: подождите {error.seconds} сек."
			await self._abandon_temp_session(state)
			return state
		except PhoneNumberInvalidError:
			state.step = AuthStep.ERROR
			state.error = "Неверный номер телефона"
			await self._abandon_temp_session(state)
			return state
		except Exception as error:
			message = self._format_phone_error(error)
			state.step = AuthStep.ERROR
			state.error = message
			await self._abandon_temp_session(state)
			return state

	async def _try_reuse_account_session(
		self,
		state: LoginState,
		phone: str,
		account_base: str,
	) -> LoginState | None:
		"""Вернуть LoginState, если account.session жив и уже авторизован; иначе None."""
		if not os.path.exists(f"{account_base}.session"):
			return None
		client = ClientFactory.create(
			account_base, proxy=state.proxy, device=state.device_params
		)
		state.client = client
		state.phone = phone
		state.session_path = f"{account_base}.session"
		save_device_params(account_base, state.device_params)
		try:
			await self._connect_with_lock_retry(client, account_base, attempts=2)
			if not await client.is_user_authorized():
				await self._safe_disconnect(state)
				state.session_path = None
				return None

			me = await client.get_me()
			self._apply_me(state, me)
			account_key = str(me.phone or me.id)
			saved = await cloud_secrets.get(account_key)
			if saved:
				try:
					await self._verify_cloud_password(client, saved)
					state.cloud_password = saved
					state.step = AuthStep.DONE
					state.error = None
					return state
				except Exception:
					await cloud_secrets.delete(account_key)
			if await self._account_has_2fa(client):
				state.step = AuthStep.PASSWORD
				state.error = None
				return state
			state.step = AuthStep.DONE
			state.error = None
			return state
		except Exception as error:
			await self._safe_disconnect(state)
			state.session_path = None
			if self._is_db_locked(error):
				# account.session занят другим процессом — отправим код через temp
				return None
			# иные ошибки при открытии старой сессии — тоже fallback на новый код
			return None

	def _format_phone_error(self, error: BaseException) -> str:
		message = str(error)
		if self._is_db_locked(error):
			return (
				"Сессия Telegram занята другим процессом. "
				"Оставьте один запуск сервера и повторите."
			)
		if "UPDATE_APP_TO_LOGIN" in message:
			return (
				"Telegram отклонил клиент (UPDATE_APP_TO_LOGIN). "
				"Нужен актуальный Telethon и свои api_id/api_hash с my.telegram.org. "
				f"Детали: {error}"
			)
		if (
			isinstance(error, (asyncio.TimeoutError, TimeoutError))
			or "timed out" in message.lower()
			or "TimeoutError" in message
		):
			return (
				"Не удалось подключиться к Telegram (таймаут). "
				"Проверьте BOT_PROXY / прокси в настройках бота."
			)
		return message

	async def submit_code(self, login_id: str, code: str) -> LoginState:
		state = self._require(login_id)
		if not state.client or not state.phone:
			state.step = AuthStep.ERROR
			state.error = "Сначала укажите номер телефона"
			return state

		code = (code or "").strip()
		if not code:
			state.error = "Введите код из SMS / Telegram"
			state.step = AuthStep.CODE
			return state

		try:
			await state.client.sign_in(
				phone=state.phone,
				code=code,
				phone_code_hash=state.phone_code_hash,
			)
			me = await state.client.get_me()
			self._apply_me(state, me)
			state.step = AuthStep.DONE
			state.error = None
			return state
		except SessionPasswordNeededError:
			state.step = AuthStep.PASSWORD
			state.error = None
			return state
		except PhoneCodeInvalidError:
			state.step = AuthStep.CODE
			state.error = "Неверный код"
			return state
		except PhoneCodeExpiredError:
			state.step = AuthStep.ERROR
			state.error = "Код истёк. Начните вход заново"
			await self._safe_disconnect(state)
			return state
		except Exception as error:
			state.step = AuthStep.ERROR
			state.error = str(error)
			await self._safe_disconnect(state)
			return state

	async def submit_password(self, login_id: str, password: str) -> LoginState:
		state = self._require(login_id)
		if not state.client:
			state.step = AuthStep.ERROR
			state.error = "Сессия входа не найдена"
			return state

		password = (password or "").strip()
		if not password:
			state.step = AuthStep.PASSWORD
			state.error = "Введите пароль 2FA"
			return state

		try:
			if await state.client.is_user_authorized():
				await self._verify_cloud_password(state.client, password)
			else:
				await state.client.sign_in(password=password)

			me = await state.client.get_me()
			self._apply_me(state, me)
			# иначе finish() → cleanup_orphan удалит phone_*.session до миграции
			await self._persist_session_as_account(state)
			state.cloud_password = password
			await cloud_secrets.set(str(me.phone or me.id), password)
			state.step = AuthStep.DONE
			state.error = None
			return state
		except PasswordHashInvalidError:
			state.step = AuthStep.PASSWORD
			state.error = "Неверный пароль 2FA"
			return state
		except Exception as error:
			msg = str(error).lower()
			if "password" in msg and ("invalid" in msg or "hash" in msg):
				state.step = AuthStep.PASSWORD
				state.error = "Неверный пароль 2FA"
				return state
			state.step = AuthStep.ERROR
			state.error = str(error)
			await self._safe_disconnect(state)
			return state

	async def start_qr(
		self,
		login_id: str,
		proxy_raw: Optional[str] = None,
		options: Optional[ExportOptions] = None,
	) -> LoginState:
		state = self._require(login_id)
		if options:
			state.options = options

		try:
			state.proxy = ProxySettings.resolve(proxy_raw)
		except ValueError as error:
			state.step = AuthStep.ERROR
			state.error = f"Прокси: {error}"
			return state

		await self._abandon_temp_qr_session(state)
		self._clear_qr(state)

		session_base = os.path.join(self.SESSIONS_DIR, f"qr_{login_id}")
		self._unlink_session(session_base)
		client = ClientFactory.create(
			session_base, proxy=state.proxy, device=state.device_params
		)
		state.client = client
		state.session_path = f"{session_base}.session"
		save_device_params(session_base, state.device_params)
		state.phone = None
		state.phone_code_hash = None

		try:
			await client.connect()
			qr = await client.qr_login()
			state.qr_login = qr
			self._publish_qr(state, qr)
			state.step = AuthStep.QR
			state.error = None
			return state
		except FloodWaitError as error:
			state.step = AuthStep.ERROR
			state.error = f"FloodWait: подождите {error.seconds} сек."
			await self._abandon_temp_qr_session(state)
			return state
		except Exception as error:
			message = str(error)
			if isinstance(error, (asyncio.TimeoutError, TimeoutError)) or "timed out" in message.lower() or "TimeoutError" in type(error).__name__ or not message:
				message = (
					"Не удалось подключиться к Telegram (таймаут). "
					"Проверьте BOT_PROXY в .env или прокси в настройках бота."
				)
			state.step = AuthStep.ERROR
			state.error = message
			await self._abandon_temp_qr_session(state)
			return state

	async def poll_qr(self, login_id: str) -> LoginState:
		state = self._require(login_id)
		if state.step in (AuthStep.DONE, AuthStep.PASSWORD, AuthStep.ERROR):
			return state
		# ушли на телефон / другой шаг — не превращаем в ERROR «QR не активен»
		if state.step != AuthStep.QR:
			return state
		if not state.client or not state.qr_login:
			state.step = AuthStep.ERROR
			state.error = "QR-сессия не найдена"
			return state

		qr = state.qr_login
		try:
			if self._qr_expired(qr):
				await qr.recreate()
				self._publish_qr(state, qr)

			timeout = self._qr_wait_timeout(qr)
			user = await qr.wait(timeout=timeout)
			return await self._finalize_authorized(state, user)
		except asyncio.TimeoutError:
			self._publish_qr(state, qr)
			state.step = AuthStep.QR
			state.error = None
			return state
		except SessionPasswordNeededError:
			state.step = AuthStep.PASSWORD
			state.error = None
			self._clear_qr_visual(state)
			return state
		except FloodWaitError as error:
			state.step = AuthStep.ERROR
			state.error = f"FloodWait: подождите {error.seconds} сек."
			await self._abandon_temp_qr_session(state)
			return state
		except Exception as error:
			msg = str(error).lower()
			if "token" in msg or "expired" in msg or "unexpected" in msg:
				try:
					await qr.recreate()
					self._publish_qr(state, qr)
					state.step = AuthStep.QR
					state.error = None
					return state
				except Exception as recreate_error:
					state.step = AuthStep.ERROR
					state.error = str(recreate_error)
					await self._abandon_temp_qr_session(state)
					return state
			state.step = AuthStep.ERROR
			state.error = str(error)
			await self._abandon_temp_qr_session(state)
			return state

	async def finish(self, login_id: str) -> None:
		state = login_store.get(login_id)
		if not state:
			self.cleanup_orphan_qr_sessions()
			return
		# путь аккаунта после persist — не трогаем при orphan-cleanup
		keep_bases: set[str] = set()
		if state.step in (AuthStep.DONE, AuthStep.PASSWORD) and state.session_path:
			base = (
				state.session_path[:-8]
				if state.session_path.endswith(".session")
				else state.session_path
			)
			keep_bases.add(os.path.abspath(base))
			# на случай если persist ещё не сработал — не сносим phone_*/qr_* этой сессии
			temp = self._temp_session_base(state.session_path)
			if temp:
				keep_bases.add(os.path.abspath(temp))

		if (
			self._temp_qr_session_base(state.session_path)
			and state.step not in (AuthStep.DONE, AuthStep.PASSWORD)
		):
			await self._abandon_temp_qr_session(state)
		else:
			await self._safe_disconnect(state)
		login_store.remove(login_id)
		self.cleanup_orphan_temp_sessions(keep_bases=keep_bases)

	def cleanup_orphan_temp_sessions(self, keep_bases: set[str] | None = None) -> int:
		"""Удалить qr_*/phone_* файлы, не привязанные к активному login_id."""
		alive: set[str] = set(keep_bases or ())
		for item in login_store._items.values():
			base = self._temp_session_base(item.session_path)
			if base:
				alive.add(os.path.abspath(base))

		removed = 0
		try:
			names = os.listdir(self.SESSIONS_DIR)
		except OSError:
			return 0

		bases: set[str] = set()
		for name in names:
			if not (name.startswith("qr_") or name.startswith("phone_")):
				continue
			if name.endswith(".session-journal"):
				bases.add(name[: -len(".session-journal")])
			elif name.endswith(".device.json"):
				bases.add(name[: -len(".device.json")])
			elif name.endswith(".session"):
				bases.add(name[: -len(".session")])

		for base_name in bases:
			base_path = os.path.join(self.SESSIONS_DIR, base_name)
			if os.path.abspath(base_path) in alive:
				continue
			self._unlink_session(base_path)
			removed += 1
		return removed

	def cleanup_orphan_qr_sessions(self) -> int:
		return self.cleanup_orphan_temp_sessions()

	async def discard_qr(self, login_id: str) -> None:
		"""Уход с QR на телефон: удалить qr_*.session, login_id оставить."""
		state = login_store.get(login_id)
		if not state:
			self.cleanup_orphan_qr_sessions()
			return
		await self._abandon_temp_qr_session(state)
		if state.step == AuthStep.QR:
			state.step = AuthStep.PHONE
			state.error = None
		self.cleanup_orphan_qr_sessions()

	def _require(self, login_id: str) -> LoginState:
		state = login_store.get(login_id)
		if not state:
			raise KeyError("login_id не найден — обновите страницу")
		return state

	async def _finalize_authorized(self, state: LoginState, user=None) -> LoginState:
		if user is None:
			user = await state.client.get_me()
		self._apply_me(state, user)
		await self._persist_session_as_account(state)
		account_key = str(user.phone or user.id)
		saved = await cloud_secrets.get(account_key)
		if saved:
			try:
				await self._verify_cloud_password(state.client, saved)
				state.cloud_password = saved
				state.step = AuthStep.DONE
				state.error = None
				self._clear_qr_visual(state)
				return state
			except Exception:
				await cloud_secrets.delete(account_key)
		if await self._account_has_2fa(state.client):
			state.step = AuthStep.PASSWORD
			state.error = None
			self._clear_qr_visual(state)
			return state
		state.step = AuthStep.DONE
		state.error = None
		self._clear_qr_visual(state)
		return state

	async def _persist_session_as_account(self, state: LoginState) -> None:
		if not state.client or not state.session_path:
			return
		account = state.phone or (str(state.user_id) if state.user_id else None)
		if not account:
			return
		# только цифры — безопасное имя файла
		account = "".join(ch for ch in str(account) if ch.isalnum() or ch in ("_", "-"))
		if not account:
			return
		old_base = (
			state.session_path[:-8]
			if state.session_path.endswith(".session")
			else state.session_path
		)
		new_base = os.path.join(self.SESSIONS_DIR, account)
		if os.path.abspath(old_base) == os.path.abspath(new_base):
			return
		proxy = state.proxy
		await self._safe_disconnect(state)
		self._unlink_session(new_base)
		for suffix in (".session", ".session-journal", ".device.json"):
			src = f"{old_base}{suffix}"
			dst = f"{new_base}{suffix}"
			if os.path.exists(src):
				os.replace(src, dst)
		save_device_params(new_base, state.device_params)
		client = ClientFactory.create(
			new_base, proxy=proxy, device=state.device_params
		)
		await client.connect()
		state.client = client
		state.session_path = f"{new_base}.session"
		state.proxy = proxy

	@staticmethod
	def _unlink_session(base: str) -> None:
		for path in (
			f"{base}.session",
			f"{base}.session-journal",
			f"{base}.device.json",
		):
			try:
				if os.path.exists(path):
					os.remove(path)
			except OSError:
				pass

	@classmethod
	def _temp_session_base(cls, session_path: str | None) -> str | None:
		"""База временных файлов: qr_* и phone_{login_id}."""
		if not session_path:
			return None
		name = os.path.basename(session_path)
		if name.endswith(".session"):
			name = name[: -len(".session")]
		if not (name.startswith("qr_") or name.startswith("phone_")):
			return None
		return os.path.join(cls.SESSIONS_DIR, name)

	@classmethod
	def _temp_qr_session_base(cls, session_path: str | None) -> str | None:
		return cls._temp_session_base(session_path)

	@classmethod
	def _unlink_temp_session(cls, session_path: str | None) -> None:
		base = cls._temp_session_base(session_path)
		if base:
			cls._unlink_session(base)

	async def _abandon_temp_session(self, state: LoginState) -> None:
		"""Отключить клиент и удалить qr_*/phone_*.session, если вход не сохранён."""
		path = state.session_path
		await self._safe_disconnect(state)
		self._unlink_temp_session(path)
		if self._temp_session_base(path):
			state.session_path = None
		self._clear_qr(state)

	async def _abandon_temp_qr_session(self, state: LoginState) -> None:
		await self._abandon_temp_session(state)

	@staticmethod
	def _clear_qr(state: LoginState) -> None:
		state.qr_login = None
		WebAuthService._clear_qr_visual(state)

	@staticmethod
	def _clear_qr_visual(state: LoginState) -> None:
		state.qr_url = None
		state.qr_svg = None
		state.qr_expires = None

	@staticmethod
	def _publish_qr(state: LoginState, qr) -> None:
		state.qr_url = qr.url
		state.qr_svg = WebAuthService._qr_svg(qr.url)
		expires = qr.expires
		if isinstance(expires, datetime):
			if expires.tzinfo is None:
				expires = expires.replace(tzinfo=timezone.utc)
			state.qr_expires = expires.isoformat()
		else:
			state.qr_expires = str(expires)

	@staticmethod
	def _qr_svg(url: str) -> str:
		from web.services.qr_style import default_logo_path, render_telegram_style_qr

		return render_telegram_style_qr(url, logo_path=default_logo_path())

	@staticmethod
	def _qr_expired(qr) -> bool:
		expires = qr.expires
		if not isinstance(expires, datetime):
			return False
		if expires.tzinfo is None:
			expires = expires.replace(tzinfo=timezone.utc)
		return datetime.now(timezone.utc) >= expires

	@staticmethod
	def _qr_wait_timeout(qr) -> float:
		expires = qr.expires
		if not isinstance(expires, datetime):
			return 2.0
		if expires.tzinfo is None:
			expires = expires.replace(tzinfo=timezone.utc)
		remaining = (expires - datetime.now(timezone.utc)).total_seconds()
		return max(0.4, min(2.0, remaining))

	@staticmethod
	async def _account_has_2fa(client) -> bool:
		try:
			pwd = await client(functions.account.GetPasswordRequest())
			return bool(getattr(pwd, "has_password", False))
		except Exception:
			return False

	@staticmethod
	async def _verify_cloud_password(client, password: str) -> None:
		pwd = await client(functions.account.GetPasswordRequest())
		if not getattr(pwd, "has_password", False):
			return
		await client(
			functions.account.GetPasswordSettingsRequest(
				password=compute_check(pwd, password)
			)
		)

	@staticmethod
	def _is_db_locked(error: BaseException) -> bool:
		msg = str(error or "").lower()
		name = type(error).__name__.lower()
		return "database is locked" in msg or ("locked" in msg and "operational" in name)

	@staticmethod
	def _session_paths(base: str) -> tuple[str, str]:
		return f"{base}.session", f"{base}.session-journal"

	@classmethod
	def _checkpoint_session_file(cls, base: str) -> None:
		"""Снять WAL/journal у .session, если файл не эксклюзивно занят."""
		import sqlite3

		session_path, journal_path = cls._session_paths(base)
		if not os.path.exists(session_path):
			cls._unlink_session(base)
			return
		try:
			conn = sqlite3.connect(session_path, timeout=2)
			try:
				conn.execute("PRAGMA busy_timeout=2000")
				conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
				conn.commit()
			finally:
				conn.close()
		except Exception:
			pass
		if os.path.exists(journal_path):
			try:
				os.remove(journal_path)
			except OSError:
				pass

	@classmethod
	def _clear_stale_session_journal(cls, base: str) -> None:
		cls._checkpoint_session_file(base)

	async def _disconnect_session_holders(self, session_base: str) -> None:
		"""Отключить все LoginState, у которых открыт тот же .session файл."""
		target = os.path.abspath(f"{session_base}.session")
		for other in list(login_store._items.values()):
			path = getattr(other, "session_path", None) or ""
			if not path:
				continue
			if os.path.abspath(path) != target:
				continue
			if other.client is None:
				continue
			await self._safe_disconnect(other)

	async def _connect_with_lock_retry(self, client, session_base: str, *, attempts: int = 4) -> None:
		last_error: BaseException | None = None
		for attempt in range(attempts):
			try:
				await client.connect()
				return
			except Exception as error:
				last_error = error
				if not self._is_db_locked(error):
					raise
				await asyncio.sleep(0.35 * (attempt + 1))
				try:
					await client.disconnect()
				except Exception:
					pass
				await self._disconnect_session_holders(session_base)
				self._clear_stale_session_journal(session_base)
		assert last_error is not None
		raise last_error

	@staticmethod
	async def _safe_disconnect(state: LoginState) -> None:
		state.qr_login = None
		if not state.client:
			return
		try:
			await state.client.disconnect()
		except Exception:
			pass
		state.client = None

	@staticmethod
	def _apply_me(state: LoginState, user) -> None:
		state.user_label = WebAuthService._label(user)
		state.user_id = int(user.id) if getattr(user, "id", None) else None
		state.username = (user.username or None) if getattr(user, "username", None) else None
		if getattr(user, "phone", None):
			state.phone = str(user.phone)

	@staticmethod
	def _label(user) -> str:
		parts = [user.first_name or "", user.last_name or ""]
		name = " ".join(p for p in parts if p).strip() or "без имени"
		username = f" @{user.username}" if user.username else ""
		phone = f" (+{user.phone})" if user.phone else ""
		return f"{name}{username}{phone}"
