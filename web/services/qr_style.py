from __future__ import annotations

from pathlib import Path
from typing import List, Sequence, Set, Tuple

import segno

Point = Tuple[int, int]


def render_telegram_style_qr(
	payload: str,
	*,
	logo_path: Path | None = None,
	module_px: int | None = None,
	border: int = 3,
	size_px: int = 240,
) -> str:
	"""
	QR в духе Telegram Web K:
	фон #eef6fd, скруглённые «глазки», модули-кружки, логотип в центре.
	"""
	qr = segno.make(payload, error="h")
	matrix: List[Sequence[int]] = [list(row) for row in qr.matrix]
	n = len(matrix)
	if module_px is None:
		module_px = max(4, size_px // (n + border * 2))
	finder_cells = _finder_cells(n)
	logo_cells = _logo_hole_cells(n)

	outer = (n + border * 2) * module_px
	radius = module_px * 2.4
	parts: List[str] = [
		f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {outer} {outer}" '
		f'width="{size_px}" height="{size_px}" role="img" aria-label="QR">',
		f'<rect width="{outer}" height="{outer}" rx="{radius}" ry="{radius}" fill="#eef6fd"/>',
	]

	# «глазки»
	for ox, oy in ((0, 0), (n - 7, 0), (0, n - 7)):
		parts.append(_finder_svg(ox, oy, border, module_px))

	# модули (не глаз и не под лого)
	r = module_px * 0.42
	for y, row in enumerate(matrix):
		for x, bit in enumerate(row):
			if not bit:
				continue
			if (x, y) in finder_cells or (x, y) in logo_cells:
				continue
			cx = (x + border) * module_px + module_px / 2
			cy = (y + border) * module_px + module_px / 2
			parts.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="#000000"/>')

	# белая подложка + логотип
	parts.append(_logo_overlay(n, border, module_px, logo_path))
	parts.append("</svg>")
	return "".join(parts)


def _finder_cells(n: int) -> Set[Point]:
	cells: Set[Point] = set()
	for ox, oy in ((0, 0), (n - 7, 0), (0, n - 7)):
		for y in range(7):
			for x in range(7):
				cells.add((ox + x, oy + y))
	return cells


def _logo_hole_cells(n: int) -> Set[Point]:
	"""Очищаем центр под лого (круг), чтобы не мешать сканированию."""
	cx = (n - 1) / 2
	cy = (n - 1) / 2
	radius = max(3.2, n * 0.18)
	cells: Set[Point] = set()
	r2 = radius * radius
	for y in range(n):
		for x in range(n):
			if (x - cx) ** 2 + (y - cy) ** 2 <= r2:
				cells.add((x, y))
	return cells


def _finder_svg(ox: int, oy: int, border: int, m: int) -> str:
	"""Скруглённый finder 7×7 как в Telegram."""
	x = (ox + border) * m
	y = (oy + border) * m
	outer_r = m * 1.35
	mid_r = m * 1.0
	inner_r = m * 0.75
	return (
		f'<rect x="{x}" y="{y}" width="{7 * m}" height="{7 * m}" '
		f'rx="{outer_r}" ry="{outer_r}" fill="#000"/>'
		f'<rect x="{x + m}" y="{y + m}" width="{5 * m}" height="{5 * m}" '
		f'rx="{mid_r}" ry="{mid_r}" fill="#eef6fd"/>'
		f'<rect x="{x + 2 * m}" y="{y + 2 * m}" width="{3 * m}" height="{3 * m}" '
		f'rx="{inner_r}" ry="{inner_r}" fill="#000"/>'
	)


def _logo_overlay(n: int, border: int, m: int, logo_path: Path | None) -> str:
	cx = (border + n / 2) * m
	cy = (border + n / 2) * m
	logo_d = max(m * 7.5, n * m * 0.28)
	pad = logo_d * 0.12
	disk = logo_d / 2 + pad
	chunks = [
		f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{disk:.2f}" fill="#ffffff"/>',
	]
	if logo_path and logo_path.is_file():
		import base64

		raw = logo_path.read_bytes()
		b64 = base64.b64encode(raw).decode("ascii")
		x = cx - logo_d / 2
		y = cy - logo_d / 2
		chunks.append(
			f'<image href="data:image/svg+xml;base64,{b64}" '
			f'x="{x:.2f}" y="{y:.2f}" width="{logo_d:.2f}" height="{logo_d:.2f}" '
			f'preserveAspectRatio="xMidYMid meet"/>'
		)
	else:
		# fallback: синий круг как у TG
		chunks.append(
			f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{logo_d * 0.48:.2f}" fill="#3390ec"/>'
		)
	return "".join(chunks)


def default_logo_path() -> Path:
	return Path(__file__).resolve().parents[2] / "landing" / "static" / "tg-login" / "logo.svg"
