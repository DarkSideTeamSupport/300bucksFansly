import os
from pathlib import Path


def load_dotenv(path: str = ".env") -> None:
	file_path = Path(path)
	if not file_path.exists():
		return
	for line in file_path.read_text(encoding="utf-8").splitlines():
		line = line.strip()
		if not line or line.startswith("#") or "=" not in line:
			continue
		key, value = line.split("=", 1)
		os.environ.setdefault(key.strip(), value.strip())


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_CHAT_IDS = os.getenv("ADMIN_CHAT_IDS", "").strip()
if not BOT_TOKEN:
	raise RuntimeError("Укажите BOT_TOKEN в .env")
