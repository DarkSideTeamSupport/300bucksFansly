import os, asyncio, time, datetime
from app.account_login import AccountLogin
from app.session_manager import SessionManager


async def on_startup(config):
	loading(config)
	await ensure_sessions(config)
	if not config.load_sessions:
		print("- Нет .session файлов. Завершение.")
		return

	ask_delete_invalid(config)

	config.process_timer = int(time.time())
	semaphore = asyncio.Semaphore(3)
	config.process = True
	tasks = [semaphore_process(semaphore, i, config) for i in config.load_sessions] + [view(config)]
	await asyncio.gather(*tasks)
	config.process = False
	on_shutdown(config)


async def ensure_sessions(config):
	if config.load_sessions:
		if ask_yes_no("- Добавить ещё аккаунт через вход?"):
			await AccountLogin().run()
			config.load_sessions = load_sessions()
			print(f"- Загружено сессий: \t{len(config.load_sessions)}\n")
		return

	print("- Нет .session файлов в папке sessions.")
	if not ask_yes_no("- Войти в аккаунт и создать сессию?"):
		return

	session_path = await AccountLogin().run()
	if not session_path:
		return

	config.load_sessions = load_sessions()
	print(f"- Загружено сессий: \t{len(config.load_sessions)}\n")


def ask_yes_no(prompt: str) -> bool:
	while True:
		value = input(f"{prompt} [y/n]: ").strip().lower()
		if value in ("y", "н", "yes", "да"):
			return True
		if value in ("n", "т", "no", "нет"):
			return False
		print("- Неизвестная команда.\n")


def ask_delete_invalid(config):
	while True:
		print("- Хотите ли Вы удалить невалидные сессии?")
		select_status = input("Введите значение [y/n]: ").lower()

		if select_status in ("y", "н"):
			print("- Невалидные сессии будут удалены.\n")
			config.delete_invalid_sessions = True
			return
		if select_status in ("n", "т"):
			print("- Невалидные сессии будут сохранены.\n")
			config.delete_invalid_sessions = False
			return
		print("- Неизвестная команда.\n")
	

async def semaphore_process(semaphore, session, config):
    await semaphore.acquire()
    try:
        await asyncio.wait_for(process(session, config), config.limit_timer_process)
    except asyncio.TimeoutError:
        semaphore.release()
        return
    if config.count_checker == len(config.load_sessions): config.process = False
    semaphore.release()
	

async def process(session, config):
	try:
		config.count_checker += 1
		obj = SessionManager(session, config)
		if not await obj.is_valid():
			try:
				await obj.client.disconnect()
			except:
				pass
			delete_session(session, config)
		else:
			name_session = str(session.split('/')[1].split('.')[0]) + "_" + str(datetime.datetime.now()).split('.')[0].replace(':', '_')
			await obj.start_dump(name_session.replace(' ', '_'))
			config.count_valid_sessions += 1
			try:
				await obj.client.disconnect()
			except:
				pass
	except Exception as e:
		print(e)
		delete_session(session, config)
	


async def view(config):
	while config.process:
		await asyncio.sleep(1)
		now = int(time.time())
		value = int(config.count_checker/len(config.load_sessions)*100) if config.count_checker else 0
		print(f"\r[{value}%] Проверено/Дамп/Невалид - {config.count_checker}/{config.count_valid_sessions}/{config.count_invalid_sessions} | {now - config.process_timer} sec", end = "	")
	return True



def load_sessions():
	os.makedirs("sessions", exist_ok=True)
	return [f"sessions/{i}" for i in os.listdir("sessions") if i.endswith(".session")]


def delete_session(session, config):
	config.count_invalid_sessions += 1
	if config.delete_invalid_sessions:
		os.remove(session)


def loading(config):
	print("\u000a\u2591\u2588\u2588\u2588\u2588\u2588\u2588\u2557\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2557\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2557\u2591\u2588\u2588\u2588\u2588\u2588\u2557\u2591\u2588\u2588\u2557\u2591\u2591\u2591\u2591\u2591\u000a\u2588\u2588\u2554\u2550\u2550\u2550\u2550\u255d\u255a\u2550\u2550\u2588\u2588\u2554\u2550\u2550\u255d\u2588\u2588\u2554\u2550\u2550\u2550\u2550\u255d\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2557\u2588\u2588\u2551\u2591\u2591\u2591\u2591\u2591\u000a\u255a\u2588\u2588\u2588\u2588\u2588\u2557\u2591\u2591\u2591\u2591\u2588\u2588\u2551\u2591\u2591\u2591\u2588\u2588\u2588\u2588\u2588\u2557\u2591\u2591\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2551\u2588\u2588\u2551\u2591\u2591\u2591\u2591\u2591\u000a\u2591\u255a\u2550\u2550\u2550\u2588\u2588\u2557\u2591\u2591\u2591\u2588\u2588\u2551\u2591\u2591\u2591\u2588\u2588\u2554\u2550\u2550\u255d\u2591\u2591\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2551\u2588\u2588\u2551\u2591\u2591\u2591\u2591\u2591\u000a\u2588\u2588\u2588\u2588\u2588\u2588\u2554\u255d\u2591\u2591\u2591\u2588\u2588\u2551\u2591\u2591\u2591\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2557\u2588\u2588\u2551\u2591\u2591\u2588\u2588\u2551\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2557\u000a\u255a\u2550\u2550\u2550\u2550\u2550\u255d\u2591\u2591\u2591\u2591\u255a\u2550\u255d\u2591\u2591\u2591\u255a\u2550\u2550\u2550\u2550\u2550\u2550\u255d\u255a\u2550\u255d\u2591\u2591\u255a\u2550\u255d\u255a\u2550\u2550\u2550\u2550\u2550\u2550\u255d\u000a\u000a\u2591\u2591\u2591\u2591\u2588\u2588\u2557\u2588\u2588\u2588\u2588\u2588\u2588\u2557\u2591\u2591\u2588\u2588\u2588\u2588\u2588\u2557\u2591\u2588\u2588\u2588\u2588\u2588\u2588\u2557\u2591\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2557\u000a\u2591\u2591\u2591\u2588\u2588\u2554\u255d\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2557\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2557\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2557\u255a\u2550\u2550\u2588\u2588\u2554\u2550\u2550\u255d\u000a\u2591\u2591\u2588\u2588\u2554\u255d\u2591\u2588\u2588\u2588\u2588\u2588\u2588\u2554\u255d\u2588\u2588\u2551\u2591\u2591\u2588\u2588\u2551\u2588\u2588\u2588\u2588\u2588\u2588\u2554\u255d\u2591\u2591\u2591\u2588\u2588\u2551\u2591\u2591\u2591\u000a\u2591\u2588\u2588\u2554\u255d\u2591\u2591\u2588\u2588\u2554\u2550\u2550\u2550\u255d\u2591\u2588\u2588\u2551\u2591\u2591\u2588\u2588\u2551\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2557\u2591\u2591\u2591\u2588\u2588\u2551\u2591\u2591\u2591\u000a\u2588\u2588\u2554\u255d\u2591\u2591\u2591\u2588\u2588\u2551\u2591\u2591\u2591\u2591\u2591\u255a\u2588\u2588\u2588\u2588\u2588\u2554\u255d\u2588\u2588\u2551\u2591\u2591\u2588\u2588\u2551\u2591\u2591\u2591\u2588\u2588\u2551\u2591\u2591\u2591\u000a\u255a\u2550\u255d\u2591\u2591\u2591\u2591\u255a\u2550\u255d\u2591\u2591\u2591\u2591\u2591\u2591\u255a\u2550\u2550\u2550\u2550\u255d\u2591\u255a\u2550\u255d\u2591\u2591\u255a\u2550\u255d\u2591\u2591\u2591\u255a\u2550\u255d\u2591\u2591\u2591\n\n\u00b7\u0020\u0054\u0065\u006c\u0065\u0067\u0072\u0061\u006d\u003a\u0020\u0040\u0073\u0074\u0065\u0061\u006c\u0070\u006f\u0072\u0074\n")
	print(config.name)
	config.load_sessions = load_sessions()
	print(f"\n- Загружено сессий: \t{len(config.load_sessions)}\n")
	print(f"- Дамп фото: \t\t{config.dump_photo}")
	print(f"- Дамп видео: \t\t{config.dump_video} (max {config.dump_max_size_video} MB)")
	print(f"- Дамп голосовых: \t{config.dump_voice_message}\n")
	print(f"- Лимит на одну сессию:\t{config.limit_timer_process} sec\n")
	return True



def on_shutdown(config):
	print('\n\n\n')
	now = int(time.time())
	text = [
		f"--- Процесс занял {now - config.process_timer} секунд ---\n",
		f"[1] Проверено сессий - {config.count_checker}",
		f"[2] Дамп сессий - {config.count_valid_sessions}",
		f"[3] Невалидные сессии - {config.count_invalid_sessions}\n"		
	]
	text += [f"- Невалидные сессии были удалены ({config.count_invalid_sessions})" if config.delete_invalid_sessions else "- Невалидные сессии сохранены."]
	print('\n'.join(text))