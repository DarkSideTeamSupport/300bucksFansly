import asyncio
from app.config import Config
from app.process import on_startup
from config import UserConfig

async def main():
	config = Config()

	user_config = UserConfig()
	for i in user_config.__dict__.keys():
		value = user_config.__dict__[i]
		setattr(config, i, value)

	await on_startup(config)


if __name__ == "__main__":
	asyncio.run(main())