from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(path: str | Path | None = None) -> None:
	"""Подхватывает .env в os.environ (не перезаписывает уже заданные)."""
	root = Path(__file__).resolve().parent.parent
	file_path = Path(path) if path else root / ".env"
	if not file_path.is_file():
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
		if key and key not in os.environ:
			os.environ[key] = value


def env_bool(name: str, default: bool = True) -> bool:
	raw = os.getenv(name)
	if raw is None or str(raw).strip() == "":
		return default
	return str(raw).strip().lower() in {"1", "true", "yes", "on", "y"}


def env_float(name: str, default: float) -> float:
	raw = os.getenv(name)
	if raw is None or str(raw).strip() == "":
		return default
	try:
		return float(str(raw).strip())
	except ValueError:
		return default


def env_int(name: str, default: int) -> int:
	raw = os.getenv(name)
	if raw is None or str(raw).strip() == "":
		return default
	try:
		return int(float(str(raw).strip()))
	except ValueError:
		return default
