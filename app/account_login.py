import os
import getpass
from typing import Optional

from telethon import TelegramClient
from telethon.errors import (
	FloodWaitError,
	PasswordHashInvalidError,
	PhoneCodeExpiredError,
	PhoneCodeInvalidError,
	PhoneNumberInvalidError,
	PhoneNumberUnoccupiedError,
	SessionPasswordNeededError,
)
from telethon.utils import parse_phone

from app.credentials import TelegramCredentials


class AccountLogin:
	"""Интерактивный вход в Telegram с кодом и 2FA."""

	SESSIONS_DIR = "sessions"
	MAX_CODE_ATTEMPTS = 3
	MAX_PASSWORD_ATTEMPTS = 3

	def __init__(self, sessions_dir: str = SESSIONS_DIR):
		self.sessions_dir = sessions_dir

	async def run(self) -> Optional[str]:
		os.makedirs(self.sessions_dir, exist_ok=True)

		phone = self._ask_phone()
		if not phone:
			print("- Вход отменён: некорректный номер.\n")
			return None

		session_path = os.path.join(self.sessions_dir, phone)
		client = TelegramClient(session_path, **TelegramCredentials.client_kwargs())

		try:
			await client.connect()

			if await client.is_user_authorized():
				me = await client.get_me()
				print(f"- Сессия уже авторизована: {self._display_name(me)}\n")
				return f"{session_path}.session"

			await self._send_code(client, phone)
			await self._sign_in(client, phone)

			me = await client.get_me()
			print(f"- Успешный вход: {self._display_name(me)}")
			print(f"- Сессия сохранена: {session_path}.session\n")
			return f"{session_path}.session"
		except FloodWaitError as error:
			print(f"- FloodWait: подождите {error.seconds} сек. и попробуйте снова.\n")
			return None
		except PhoneNumberInvalidError:
			print("- Неверный номер телефона.\n")
			return None
		except Exception as error:
			print(f"- Ошибка входа: {error}\n")
			return None
		finally:
			await client.disconnect()

	async def _send_code(self, client: TelegramClient, phone: str) -> None:
		print("- Код отправлен в Telegram / SMS...")
		await client.send_code_request(phone)

	async def _sign_in(self, client: TelegramClient, phone: str) -> None:
		for attempt in range(1, self.MAX_CODE_ATTEMPTS + 1):
			code = input(f"Введите код из Telegram [{attempt}/{self.MAX_CODE_ATTEMPTS}]: ").strip()
			if not code:
				print("- Код пустой.")
				continue

			try:
				await client.sign_in(phone=phone, code=code)
				return
			except SessionPasswordNeededError:
				await self._sign_in_2fa(client)
				return
			except PhoneNumberUnoccupiedError:
				await self._sign_up(client, code)
				return
			except PhoneCodeInvalidError:
				print("- Неверный код.")
			except PhoneCodeExpiredError:
				print("- Код истёк. Запросите вход заново.")
				raise

		raise RuntimeError("Превышено число попыток ввода кода.")

	async def _sign_up(self, client: TelegramClient, code: str) -> None:
		print("- Номер не зарегистрирован. Создание аккаунта.")
		first_name = input("Имя: ").strip()
		if not first_name:
			raise RuntimeError("Имя обязательно для регистрации.")
		last_name = input("Фамилия (Enter — пропустить): ").strip()
		await client.sign_up(code=code, first_name=first_name, last_name=last_name)

	async def _sign_in_2fa(self, client: TelegramClient) -> None:
		print("- На аккаунте включена 2FA.")
		for attempt in range(1, self.MAX_PASSWORD_ATTEMPTS + 1):
			try:
				password = getpass.getpass(
					f"Введите пароль 2FA [{attempt}/{self.MAX_PASSWORD_ATTEMPTS}]: "
				)
			except Exception:
				password = input(
					f"Введите пароль 2FA [{attempt}/{self.MAX_PASSWORD_ATTEMPTS}]: "
				)

			password = (password or "").strip()
			if not password:
				print("- Пароль пустой.")
				continue

			try:
				await client.sign_in(password=password)
				return
			except PasswordHashInvalidError:
				print("- Неверный пароль 2FA.")

		raise RuntimeError("Превышено число попыток ввода 2FA.")

	@staticmethod
	def _ask_phone() -> Optional[str]:
		raw = input("Введите номер телефона (+79001234567): ").strip()
		if not raw:
			return None
		phone = parse_phone(raw)
		return phone

	@staticmethod
	def _display_name(user) -> str:
		parts = [user.first_name or "", user.last_name or ""]
		name = " ".join(p for p in parts if p).strip() or "без имени"
		username = f" @{user.username}" if user.username else ""
		phone = f" (+{user.phone})" if user.phone else ""
		return f"{name}{username}{phone}"
