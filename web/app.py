import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from db import close_db, init_db
from landing.app import register_landing
from web.routes.auth_routes import router as auth_router


def _setup_console_logging() -> None:
	"""Прогресс миграции/дампа видно в консоли (uvicorn)."""
	root = logging.getLogger()
	if not root.handlers:
		logging.basicConfig(
			level=logging.INFO,
			format="%(asctime)s %(levelname)s %(name)s | %(message)s",
			datefmt="%H:%M:%S",
		)
	for name in ("migration", "web.services", "landing"):
		logging.getLogger(name).setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(_app: FastAPI):
	_setup_console_logging()
	await init_db()
	from web.routes.auth_api import auth_service

	auth_service.cleanup_orphan_qr_sessions()
	logging.getLogger("migration").info("web ready — логи миграции с тегом #tg<id>")
	yield
	await close_db()


def create_app() -> FastAPI:
	app = FastAPI(
		title="TGDumper + Landing",
		docs_url=None,
		redoc_url=None,
		lifespan=lifespan,
	)
	# лендинг на /
	register_landing(app)
	# панель экспорта/миграции
	app.mount("/static", StaticFiles(directory="web/static"), name="static")
	app.include_router(auth_router)
	return app


app = create_app()
