from telethon import TelegramClient
from telethon.errors import UsernameInvalidError, UsernameOccupiedError
from telethon.tl import functions

from web.services.flood import call_with_flood_wait


class ProfileService:
	"""Смена username и bio на исходном аккаунте."""

	async def apply(
		self,
		client: TelegramClient,
		desired_username: str,
		bio: str,
	) -> dict:
		me = await client.get_me()
		result = {"username": me.username, "bio_updated": False}

		if bio is not None and bio != "":
			await call_with_flood_wait(
				lambda: client(functions.account.UpdateProfileRequest(about=bio[:70]))
			)
			result["bio_updated"] = True

		wanted = (desired_username or "").strip().lstrip("@")
		if not wanted:
			return result

		final = await self._set_username(client, wanted, me.id)
		result["username"] = final
		return result

	async def _set_username(self, client: TelegramClient, base: str, user_id: int) -> str:
		candidates = [base, f"{base}{user_id}", f"{base}_{user_id}"]
		# указанный + ID++
		for suffix in range(1, 50):
			candidates.append(f"{base}{user_id}{suffix}")

		seen = set()
		for name in candidates:
			name = "".join(ch for ch in name if ch.isalnum() or ch == "_")[:32]
			if not name or name in seen:
				continue
			seen.add(name)
			try:
				await call_with_flood_wait(
					lambda n=name: client(functions.account.UpdateUsernameRequest(n))
				)
				return name
			except UsernameOccupiedError:
				continue
			except UsernameInvalidError:
				continue
			except Exception:
				continue

		raise RuntimeError("Не удалось подобрать свободный username")
