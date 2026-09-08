import os
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

from web.services.export_options import ExportOptions
from web.services.export_service import ClientFactory
from web.services.login_store import AuthStep, LoginState, login_store
from web.services.migration.cloud_secrets import cloud_secrets
from web.services.proxy import ProxySettings


class WebAuthService:
	SESSIONS_DIR = "sessions"

	def start(self) -> LoginState:
		os.makedirs(self.SESSIONS_DIR, exist_ok=True)
		return login_store.create()

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
			state.proxy = ProxySettings.parse(proxy_raw)
		except ValueError as error:
			state.step = AuthStep.ERROR
			state.error = f"Прокси: {error}"
			return state

		phone = parse_phone((phone_raw or "").strip())
		if not phone:
			state.step = AuthStep.ERROR
			state.error = "Некорректный номер телефона"
			return state

		session_base = os.path.join(self.SESSIONS_DIR, phone)
		client = ClientFactory.create(session_base, proxy=state.proxy)
		state.client = client
		state.phone = phone
		state.session_path = f"{session_base}.session"

		try:
			await client.connect()
			if await client.is_user_authorized():
				me = await client.get_me()
				state.user_label = self._label(me)
				account_key = str(me.phone or me.id)
				saved = await cloud_secrets.get(account_key)
				if saved:
					try:
						await self._verify_cloud_password(client, saved)
						state.cloud_password = saved
						state.step = AuthStep.DONE
						return state
					except Exception:
						# сохранённый пароль устарел / неверный — спросим снова
						await cloud_secrets.delete(account_key)
				if await self._account_has_2fa(client):
					state.step = AuthStep.PASSWORD
					state.error = None
					return state
				state.step = AuthStep.DONE
				return state

			sent = await client.send_code_request(phone)
			state.phone_code_hash = sent.phone_code_hash
			state.step = AuthStep.CODE
			state.error = None
			return state
		except FloodWaitError as error:
			state.step = AuthStep.ERROR
			state.error = f"FloodWait: подождите {error.seconds} сек."
			await self._safe_disconnect(state)
			return state
		except PhoneNumberInvalidError:
			state.step = AuthStep.ERROR
			state.error = "Неверный номер телефона"
			await self._safe_disconnect(state)
			return state
		except Exception as error:
			message = str(error)
			if "UPDATE_APP_TO_LOGIN" in message:
				message = (
					"Telegram отклонил клиент (UPDATE_APP_TO_LOGIN). "
					"Нужен актуальный Telethon и свои api_id/api_hash с my.telegram.org. "
					f"Детали: {error}"
				)
			state.step = AuthStep.ERROR
			state.error = message
			await self._safe_disconnect(state)
			return state

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
			state.user_label = self._label(me)
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
			# Уже авторизованная сессия: только проверяем пароль и сохраняем для миграции
			if await state.client.is_user_authorized():
				await self._verify_cloud_password(state.client, password)
			else:
				await state.client.sign_in(password=password)

			me = await state.client.get_me()
			state.user_label = self._label(me)
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
			# GetPasswordSettings тоже может отдать password invalid текстом
			msg = str(error).lower()
			if "password" in msg and ("invalid" in msg or "hash" in msg):
				state.step = AuthStep.PASSWORD
				state.error = "Неверный пароль 2FA"
				return state
			state.step = AuthStep.ERROR
			state.error = str(error)
			await self._safe_disconnect(state)
			return state

	async def finish(self, login_id: str) -> None:
		state = login_store.get(login_id)
		if not state:
			return
		await self._safe_disconnect(state)
		login_store.remove(login_id)

	def _require(self, login_id: str) -> LoginState:
		state = login_store.get(login_id)
		if not state:
			raise KeyError("login_id не найден — обновите страницу")
		return state

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
	async def _safe_disconnect(state: LoginState) -> None:
		if not state.client:
			return
		try:
			await state.client.disconnect()
		except Exception:
			pass
		state.client = None

	@staticmethod
	def _label(user) -> str:
		parts = [user.first_name or "", user.last_name or ""]
		name = " ".join(p for p in parts if p).strip() or "без имени"
		username = f" @{user.username}" if user.username else ""
		phone = f" (+{user.phone})" if user.phone else ""
		return f"{name}{username}{phone}"
