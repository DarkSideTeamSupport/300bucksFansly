from telethon import TelegramClient
from telethon.tl import functions, types

from web.services.flood import call_with_flood_wait


PRIVACY_KEYS = (
	types.InputPrivacyKeyPhoneNumber,
	types.InputPrivacyKeyPhoneCall,
	types.InputPrivacyKeyPhoneP2P,
	types.InputPrivacyKeyProfilePhoto,
	types.InputPrivacyKeyStatusTimestamp,
	types.InputPrivacyKeyChatInvite,
	types.InputPrivacyKeyForwards,
	types.InputPrivacyKeyAbout,
)


class PrivacyService:
	"""Открывает приватность аккаунта (для всех)."""

	async def open_all(self, client: TelegramClient) -> list:
		results = []
		rules = [types.InputPrivacyValueAllowAll()]
		for key_cls in PRIVACY_KEYS:
			try:
				await call_with_flood_wait(
					lambda k=key_cls: client(
						functions.account.SetPrivacyRequest(key=k(), rules=rules)
					)
				)
				results.append(key_cls.__name__)
			except Exception as error:
				results.append(f"{key_cls.__name__}:error:{error}")
		return results
