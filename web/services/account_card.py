from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

_log = logging.getLogger("migration")


@dataclass
class AccountStats:
	dialogs: int = 0
	contacts: int = 0
	groups: int = 0
	channels: int = 0
	has_avatar: bool = False
	has_info: bool = False
	has_contacts_file: bool = False
	has_chats_file: bool = False
	preview_contacts: list[str] = field(default_factory=list)


def account_tag(user_id: int | str, phone: str | None = None) -> str:
	"""Тег для логов: #tg123456 (+телефон)."""
	tag = f"#tg{user_id}"
	if phone:
		return f"{tag} +{str(phone).lstrip('+')}"
	return tag


def console_log(tag: str, message: str, *, error: bool = False) -> None:
	line = f"{tag} | {message}"
	if error:
		_log.error(line)
	else:
		_log.info(line)


def build_anketa_text(
	*,
	me: Any,
	stats: AccountStats,
	folder: str,
) -> str:
	name = f"{getattr(me, 'first_name', '') or ''} {getattr(me, 'last_name', '') or ''}".strip() or "—"
	username = f"@{me.username}" if getattr(me, "username", None) else "—"
	phone = f"+{me.phone}" if getattr(me, "phone", None) else "—"
	uid = getattr(me, "id", "—")
	premium = "да" if getattr(me, "premium", False) else "нет"
	when = datetime.now().strftime("%d.%m.%Y %H:%M")

	preview = stats.preview_contacts[:8]
	preview_block = "\n".join(f"  {i}. {line}" for i, line in enumerate(preview, 1)) or "  —"

	return "\n".join(
		[
			"══════════════════════════════════",
			"         АНКЕТА АККАУНТА",
			"══════════════════════════════════",
			"",
			f"Имя:        {name}",
			f"Username:   {username}",
			f"Телефон:    {phone}",
			f"ID:         {uid}",
			f"Premium:    {premium}",
			f"Тег логов:  #tg{uid}",
			f"Дата дампа: {when}",
			"",
			"────────── Статус ──────────",
			f"Аватар:           {'✔' if stats.has_avatar else '—'}",
			f"Личные данные:    {'✔' if stats.has_info else '—'}",
			f"Контакты:         {'✔' if stats.has_contacts_file else '—'} ({stats.contacts})",
			f"Диалоги:          {stats.dialogs}",
			f"Группы:           {stats.groups}",
			f"Каналы:           {stats.channels}",
			"",
			"── Превью контактов ──",
			preview_block,
			"",
			f"Папка: {os.path.abspath(folder)}",
			"══════════════════════════════════",
			"",
		]
	)


def build_anketa_caption(*, me: Any, stats: AccountStats, html: bool = True) -> str:
	name = f"{getattr(me, 'first_name', '') or ''} {getattr(me, 'last_name', '') or ''}".strip() or "—"
	username = f"@{me.username}" if getattr(me, "username", None) else "—"
	phone = f"+{me.phone}" if getattr(me, "phone", None) else "—"
	uid = getattr(me, "id", "—")
	preview = stats.preview_contacts[:6]
	preview_lines = "\n".join(f"{i}. {p}" for i, p in enumerate(preview, 1)) or "—"

	if html:
		return (
			f"📋 <b>Анкета аккаунта</b>\n"
			f"#tg{uid}\n\n"
			f"<b>{name}</b> · {username}\n"
			f"📞 {phone}\n"
			f"🆔 <code>{uid}</code>\n\n"
			f"Фото: {'✔' if stats.has_avatar else '—'}\n"
			f"Личные данные: {'✔' if stats.has_info else '—'}\n"
			f"Контакты: <b>{stats.contacts}</b>\n"
			f"Диалоги: {stats.dialogs} · Группы: {stats.groups} · Каналы: {stats.channels}\n\n"
			f"<b>Превью контактов</b>\n{preview_lines}"
		)
	return (
		f"📋 Анкета аккаунта\n"
		f"#tg{uid}\n\n"
		f"{name} · {username}\n"
		f"📞 {phone}\n"
		f"🆔 {uid}\n\n"
		f"Фото: {'✔' if stats.has_avatar else '—'}\n"
		f"Личные данные: {'✔' if stats.has_info else '—'}\n"
		f"Контакты: {stats.contacts}\n"
		f"Диалоги: {stats.dialogs} · Группы: {stats.groups} · Каналы: {stats.channels}\n\n"
		f"Превью контактов\n{preview_lines}"
	)


def write_anketa_files(folder: str, text: str) -> str:
	path = os.path.join(folder, "anketa.txt")
	with open(path, "w", encoding="utf-8") as fh:
		fh.write(text)
	return path


def find_avatar_in_folder(folder: str) -> Optional[str]:
	if not folder or not os.path.isdir(folder):
		return None
	for name in sorted(os.listdir(folder)):
		low = name.lower()
		if low.startswith("ava") and low.endswith((".jpg", ".jpeg", ".png", ".webp")):
			return os.path.join(folder, name)
	return None


def default_placeholder_avatar() -> Optional[str]:
	"""Заглушка авы из корня проекта: ava.jpg / ava.png."""
	roots = [
		os.getcwd(),
		os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")),
	]
	names = ("ava.jpg", "ava.jpeg", "ava.png", "ava.webp")
	seen: set[str] = set()
	for root in roots:
		root = os.path.abspath(root)
		if root in seen:
			continue
		seen.add(root)
		for name in names:
			path = os.path.join(root, name)
			if os.path.isfile(path):
				return path
	return None


def resolve_avatar_path(avatar_path: Optional[str] = None, folder: str = "") -> Optional[str]:
	"""Своя ава → из папки дампа → ava.jpg/png в корне проекта."""
	if avatar_path and os.path.isfile(avatar_path):
		return avatar_path
	found = find_avatar_in_folder(folder) if folder else None
	if found:
		return found
	return default_placeholder_avatar()


def stats_from_dump_folder(folder: str) -> AccountStats:
	"""Восстановить счётчики из уже сохранённого дампа (когда export_text skipped)."""
	stats = AccountStats(has_info=False, has_contacts_file=False, has_chats_file=False)
	if not folder or not os.path.isdir(folder):
		return stats

	info = os.path.join(folder, "info.txt")
	stats.has_info = os.path.isfile(info)
	stats.has_avatar = bool(find_avatar_in_folder(folder))

	contacts = os.path.join(folder, "contacts.txt")
	if os.path.isfile(contacts):
		stats.has_contacts_file = True
		try:
			with open(contacts, encoding="utf-8") as fh:
				text = fh.read()
			# «Контакты: N» в первой строке
			import re

			m = re.search(r"Контакты:\s*(\d+)", text)
			if m:
				stats.contacts = int(m.group(1))
			# превью: «номер: …» в однострочном или старом формате
			phones = re.findall(r"номер:\s*(\+?\d+)", text)
			names = re.findall(r"имя:\s*([^|\n]+)", text)
			preview: list[str] = []
			for i, phone in enumerate(phones[:6]):
				preview.append(_mask_phone(phone))
			if len(preview) < 6:
				for name in names:
					name = name.strip()
					if name and name != "-":
						preview.append(name)
					if len(preview) >= 6:
						break
			stats.preview_contacts = preview[:6]
		except OSError:
			pass

	chats = os.path.join(folder, "chats_channels.txt")
	if os.path.isfile(chats):
		stats.has_chats_file = True
		try:
			with open(chats, encoding="utf-8") as fh:
				text = fh.read()
			import re

			mg = re.search(r"Группы:\s*(\d+)", text)
			mc = re.search(r"Каналы:\s*(\d+)", text)
			if mg:
				stats.groups = int(mg.group(1))
			if mc:
				stats.channels = int(mc.group(1))
		except OSError:
			pass

	people = os.path.join(folder, "people.txt")
	if os.path.isfile(people):
		try:
			with open(people, encoding="utf-8") as fh:
				text = fh.read()
			import re

			md = re.search(r"=== ДИАЛОГИ[^\n]*\nВсего:\s*(\d+)", text)
			if md:
				stats.dialogs = int(md.group(1))
		except OSError:
			pass

	return stats


def preview_contact_line(user: Any) -> str:
	phone = f"+{user.phone}" if getattr(user, "phone", None) else ""
	name = f"{getattr(user, 'first_name', '') or ''} {getattr(user, 'last_name', '') or ''}".strip()
	username = f"@{user.username}" if getattr(user, "username", None) else ""
	if phone:
		return _mask_phone(phone)
	return name or username or str(getattr(user, "id", "?"))


def _mask_phone(phone: str) -> str:
	"""Как на образце: +380********"""
	raw = str(phone or "").strip()
	if not raw:
		return "—"
	digits = "".join(ch for ch in raw if ch.isdigit())
	if not digits:
		return "—"
	if digits.startswith(("380", "375", "374", "994", "996", "998", "992", "993")):
		cc = digits[:3]
	elif digits.startswith(("7", "1")) and len(digits) >= 10:
		cc = digits[:1]
	else:
		cc = digits[: min(3, max(1, len(digits) - 6))]
	return f"+{cc}{'*' * 8}"


def _anketa_font(size: int):
	from PIL import ImageFont

	candidates = [
		r"C:\Windows\Fonts\segoeui.ttf",
		r"C:\Windows\Fonts\arial.ttf",
		r"C:\Windows\Fonts\tahoma.ttf",
		"/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
		"/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
	]
	for path in candidates:
		if os.path.isfile(path):
			try:
				return ImageFont.truetype(path, size=size)
			except OSError:
				continue
	return ImageFont.load_default()


def _rounded_avatar(img, size: int, radius: int = 28):
	from PIL import Image, ImageDraw

	img = img.convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
	mask = Image.new("L", (size, size), 0)
	draw = ImageDraw.Draw(mask)
	draw.rounded_rectangle((0, 0, size, size), radius=radius, fill=255)
	out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
	out.paste(img, (0, 0), mask=mask)
	return out


def render_anketa_card(
	*,
	folder: str,
	me: Any,
	stats: AccountStats,
	avatar_path: Optional[str] = None,
) -> Optional[str]:
	"""
	Карточка-анкета PNG для канала логов:
	аватар слева, статусы ✔ и превью контактов справа.
	"""
	try:
		from PIL import Image, ImageDraw
	except ImportError:
		_log.warning("Pillow не установлен — анкета-фото пропущена")
		return None

	width, height = 900, 400
	bg = (8, 12, 24)
	fg = (255, 255, 255)
	muted = (170, 180, 195)
	ok = (255, 255, 255)
	card = Image.new("RGB", (width, height), bg)
	draw = ImageDraw.Draw(card)

	font_body = _anketa_font(26)
	font_title = _anketa_font(28)
	font_small = _anketa_font(22)

	avatar_box = 300
	ax, ay = 28, (height - avatar_box) // 2
	loaded = False
	avatar_path = resolve_avatar_path(avatar_path, folder)
	if avatar_path and os.path.isfile(avatar_path):
		try:
			ava = Image.open(avatar_path)
			rounded = _rounded_avatar(ava, avatar_box, radius=26)
			card.paste(rounded, (ax, ay), rounded)
			loaded = True
		except Exception as exc:
			_log.warning("avatar load failed: %s", exc)
	if not loaded:
		draw.rounded_rectangle(
			(ax, ay, ax + avatar_box, ay + avatar_box),
			radius=26,
			fill=(32, 40, 58),
		)
		initial = (getattr(me, "first_name", None) or "?")[:1].upper()
		big = _anketa_font(84)
		bbox = draw.textbbox((0, 0), initial, font=big)
		tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
		draw.text(
			(ax + (avatar_box - tw) / 2, ay + (avatar_box - th) / 2 - 6),
			initial,
			fill=fg,
			font=big,
		)

	tx = ax + avatar_box + 40
	ty = 42
	line_gap = 34

	photo_mark = "✓" if (loaded or stats.has_avatar) else "—"
	info_mark = "✓" if stats.has_info else "—"
	draw.text((tx, ty), f"Фотографии {photo_mark}", fill=ok if photo_mark == "✓" else muted, font=font_body)
	ty += line_gap
	draw.text((tx, ty), f"Личные данные {info_mark}", fill=ok if info_mark == "✓" else muted, font=font_body)
	ty += line_gap + 4
	draw.text((tx, ty), f"Найдены контакты : {stats.contacts}", fill=fg, font=font_title)
	ty += line_gap + 14

	preview = list(stats.preview_contacts[:6])
	box_top = ty
	box_bottom = height - 28
	draw.rounded_rectangle(
		(tx - 6, box_top - 6, width - 28, box_bottom),
		radius=10,
		outline=(70, 80, 100),
		width=2,
	)

	py = box_top + 10
	if not preview:
		draw.text((tx + 10, py), "—", fill=muted, font=font_small)
	else:
		for i, line in enumerate(preview, 1):
			text = f"{i}. {line}"
			if len(text) > 36:
				text = text[:35] + "…"
			draw.text((tx + 12, py), text, fill=fg, font=font_small)
			py += 30
			if py > box_bottom - 26:
				break

	out_path = os.path.join(folder, "anketa_card.png")
	card.save(out_path, format="PNG", optimize=True)
	return out_path
