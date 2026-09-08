import os


class TelegramCredentials:
	"""api_id/api_hash: https://my.telegram.org → API development tools"""

	api_id = int(os.getenv("TG_API_ID", "19448411"))
	api_hash = os.getenv("TG_API_HASH", "0c546d07d94c271425e08e4d71c32a1c")

	@classmethod
	def client_kwargs(cls) -> dict:
		return {
			"api_id": cls.api_id,
			"api_hash": cls.api_hash,
			"device_model": os.getenv("TG_DEVICE_MODEL", "Desktop"),
			"system_version": os.getenv("TG_SYSTEM_VERSION", "Windows 10"),
			"app_version": os.getenv("TG_APP_VERSION", "1.44.0"),
			"system_lang_code": "ru",
			"lang_code": "ru",
		}
