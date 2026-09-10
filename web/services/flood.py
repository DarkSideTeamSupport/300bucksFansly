import asyncio
import random

from telethon.errors import FloodWaitError, PeerFloodError

# жёсткий потолок — иначе «перенос групп» выглядит как зависание
_MAX_FLOOD_SLEEP = 25.0
_MAX_PEER_FLOOD_SLEEP = 20.0


async def call_with_flood_wait(
	coro_factory,
	retries: int = 3,
	peer_flood_sleep: float = 12.0,
):
	"""Повторяет вызов при FloodWait / PeerFlood, с коротким потолком ожидания."""
	last_error = None
	for attempt in range(retries):
		try:
			return await coro_factory()
		except FloodWaitError as error:
			last_error = error
			wait = min(float(error.seconds) + random.uniform(0.5, 1.5), _MAX_FLOOD_SLEEP)
			await asyncio.sleep(wait)
			if error.seconds > _MAX_FLOOD_SLEEP and attempt >= 1:
				raise
		except PeerFloodError as error:
			last_error = error
			base = min(peer_flood_sleep * (attempt + 1), _MAX_PEER_FLOOD_SLEEP)
			await asyncio.sleep(base + random.uniform(0.0, 3.0))
	if last_error:
		raise last_error
	raise RuntimeError("call_with_flood_wait failed")
