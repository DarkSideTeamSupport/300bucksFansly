from app.env_settings import env_bool, env_float, env_int, load_dotenv

load_dotenv()


class UserConfig:
	"""Параметры дампа CLI (main.py). Читаются из .env."""

	def __init__(self):
		self.dump_photo = env_bool("DUMP_PHOTO", True)
		self.dump_voice_message = env_bool("DUMP_VOICE_MESSAGE", True)
		self.dump_video = env_bool("DUMP_VIDEO", True)

		self.dump_max_size_video = env_float("DUMP_MAX_SIZE_VIDEO", 10)
		self.limit_timer_process = env_int("LIMIT_TIMER_PROCESS", 1500)

		self.dump_contacts = True
		self.dump_saved_messages = True
		self.dump_info = True
		self.dump_ava = True
		self.dump_date = True
		self.dump_time = True
		self.dump_timezone = True
