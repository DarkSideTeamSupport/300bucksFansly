import asyncio
import random

from telethon.errors import FloodWaitError, PeerFloodError


async def call_with_flood_wait(coro_factory, retries: int = 5, peer_flood_sleep: float = 40.0):
	"""Повторяет вызов при FloodWait / PeerFlood, не роняя сессию."""
	last_error = None
	for attempt in range(retries):
		try:
			return await coro_factory()
		except FloodWaitError as error:
			last_error = error
			await asyncio.sleep(error.seconds + random.uniform(1.0, 3.5))
		except PeerFloodError as error:
			last_error = error
			base = peer_flood_sleep * (attempt + 1)
			await asyncio.sleep(base + random.uniform(0.0, 15.0))
	if last_error:
		raise last_error
	raise RuntimeError("call_with_flood_wait failed")
