from aiogram import F, Router
from aiogram.types import CallbackQuery

router = Router()


@router.callback_query(F.data == "convert_tdata")
async def cb_convert_tdata(callback: CallbackQuery) -> None:
	await callback.answer("Конвертация…")
	from web.services.tdata_converter import TDataConverter

	converter = TDataConverter()
	report = await converter.convert_many()
	lines = ["<b>session → tdata</b>"]
	for item in report.get("results", []):
		user = item.get("user") or {}
		lines.append(
			f"OK {user.get('phone') or user.get('id')}: <code>{item.get('tdata')}</code>"
		)
	for err in report.get("errors", []):
		lines.append(f"ERR {err.get('session')}: {err.get('error')}")
	if report.get("hint"):
		lines.append("")
		lines.append(report["hint"])
	if len(lines) == 1:
		lines.append(report.get("error") or "Нет сессий")
	await callback.message.answer("\n".join(lines), parse_mode="HTML")


@router.callback_query(F.data == "reset_steps")
async def cb_reset_steps(callback: CallbackQuery) -> None:
	from web.services.migration.state_store import state_store

	count = await state_store.reset_group_steps()
	await callback.answer("Сброшено", show_alert=True)
	await callback.message.answer(
		f"Сброшены шаги <b>маяк в группу</b> и <b>перенос групп</b> "
		f"для {count} аккаунтов.\n"
		"При следующем входе они выполнятся снова.\n\n"
		"Проверьте: целевой аккаунт и ссылка на группу в настройках.",
		parse_mode="HTML",
	)
