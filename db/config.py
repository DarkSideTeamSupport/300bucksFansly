from __future__ import annotations

import os

DB_PATH = os.path.join("data", "app.db")
DB_URL = f"sqlite://{DB_PATH.replace(os.sep, '/')}"

TORTOISE_ORM = {
	"connections": {"default": DB_URL},
	"apps": {
		"models": {
			"models": ["db.models"],
			"default_connection": "default",
		}
	},
}
