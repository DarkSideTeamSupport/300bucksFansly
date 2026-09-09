import os
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _ROOT / ".env"


def load_dotenv(path: str | Path | None = None) -> None:
	file_path = Path(path) if path else _ENV_FILE
	if not file_path.is_file():
		# fallback: cwd .env
		alt = Path(".env")
		if not alt.is_file():
			return
		file_path = alt
	for line in file_path.read_text(encoding="utf-8").splitlines():
		line = line.strip()
		if not line or line.startswith("#") or "=" not in line:
			continue
		key, value = line.split("=", 1)
		key = key.strip()
		value = value.strip().strip('"').strip("'")
		# не затираем уже заданные извне, но подтягиваем отсутствующие
		if key and key not in os.environ:
			os.environ[key] = value


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_CHAT_IDS = os.getenv("ADMIN_CHAT_IDS", "").strip()
BOT_PROXY = os.getenv("BOT_PROXY", "").strip()
if not BOT_TOKEN:
	raise RuntimeError("Укажите BOT_TOKEN в .env")
