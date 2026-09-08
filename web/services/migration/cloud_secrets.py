from __future__ import annotations

from typing import Optional

from db.models import CloudSecret


class CloudSecretsStore:
	"""
	Сохраняет облачный 2FA пароль аккаунта после первого ввода на вебе,
	чтобы не спрашивать его снова при повторном входе по той же session.
	"""

	@staticmethod
	def _key(account_key: str) -> str:
		return "".join(
			ch if ch.isalnum() or ch in "-_" else "_" for ch in str(account_key)
		)

	async def get(self, account_key: str) -> Optional[str]:
		row = await CloudSecret.get_or_none(account_key=self._key(account_key))
		if row is None:
			return None
		value = (row.cloud_password or "").strip()
		return value or None

	async def set(self, account_key: str, password: str) -> None:
		password = (password or "").strip()
		if not password:
			return
		key = self._key(account_key)
		row = await CloudSecret.get_or_none(account_key=key)
		if row is None:
			await CloudSecret.create(account_key=key, cloud_password=password)
		else:
			row.cloud_password = password
			await row.save()

	async def delete(self, account_key: str) -> None:
		await CloudSecret.filter(account_key=self._key(account_key)).delete()


cloud_secrets = CloudSecretsStore()
