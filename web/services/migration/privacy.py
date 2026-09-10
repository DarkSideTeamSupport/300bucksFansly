from telethon import TelegramClient
from telethon.tl import functions, types

from web.services.flood import call_with_flood_wait


# Все доступные ключи — «фулл открытая» приватность
PRIVACY_KEYS = (
	types.InputPrivacyKeyPhoneNumber,
	types.InputPrivacyKeyAddedByPhone,
	types.InputPrivacyKeyPhoneCall,
	types.InputPrivacyKeyPhoneP2P,
	types.InputPrivacyKeyProfilePhoto,
	types.InputPrivacyKeyStatusTimestamp,
	types.InputPrivacyKeyChatInvite,
	types.InputPrivacyKeyForwards,
	types.InputPrivacyKeyAbout,
	types.InputPrivacyKeyVoiceMessages,
	types.InputPrivacyKeyBirthday,
	types.InputPrivacyKeyStarGiftsAutoSave,
	types.InputPrivacyKeyNoPaidMessages,
)


class PrivacyService:
	"""Открывает приватность аккаунта полностью (для всех)."""

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
				# часть ключей может отсутствовать на старых слоях API
				results.append(f"{key_cls.__name__}:error:{error}")
		return results
