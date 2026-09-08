from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set

from db.models import MigrationAccountState


@dataclass
class MigrationState:
	account_key: str
	done_steps: Set[str] = field(default_factory=set)
	meta: Dict[str, str] = field(default_factory=dict)
	migrated_chats: List[int] = field(default_factory=list)

	def is_done(self, step: str) -> bool:
		return step in self.done_steps

	def mark(self, step: str) -> None:
		self.done_steps.add(step)


class StateStore:
	"""Идемпотентность: шаги миграции в SQLite."""

	async def load(self, account_key: str) -> MigrationState:
		row = await MigrationAccountState.get_or_none(account_key=account_key)
		if row is None:
			return MigrationState(account_key=account_key)
		return MigrationState(
			account_key=account_key,
			done_steps=set(row.done_steps or []),
			meta={str(k): str(v) for k, v in dict(row.meta or {}).items()},
			migrated_chats=[int(x) for x in (row.migrated_chats or [])],
		)

	async def save(self, state: MigrationState) -> None:
		payload = dict(
			done_steps=sorted(state.done_steps),
			meta=dict(state.meta),
			migrated_chats=list(state.migrated_chats),
		)
		row = await MigrationAccountState.get_or_none(account_key=state.account_key)
		if row is None:
			await MigrationAccountState.create(account_key=state.account_key, **payload)
		else:
			await row.update_from_dict(payload)
			await row.save()

	async def reset_group_steps(self) -> int:
		"""Сбрасывает notify_group / migrate_groups у всех аккаунтов."""
		count = 0
		async for row in MigrationAccountState.all():
			done = set(row.done_steps or [])
			done.discard("notify_group")
			done.discard("migrate_groups")
			row.done_steps = sorted(done)
			row.migrated_chats = []
			await row.save()
			count += 1
		return count


state_store = StateStore()
