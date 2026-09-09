from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from db import close_db, init_db
from landing.app import register_landing
from web.routes.auth_routes import router as auth_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
	await init_db()
	from web.routes.auth_api import auth_service

	auth_service.cleanup_orphan_qr_sessions()
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
