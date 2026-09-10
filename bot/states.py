from aiogram.fsm.state import State, StatesGroup


class SettingsStates(StatesGroup):
	waiting_value = State()
	waiting_log_chat_id = State()


class TargetJoinerStates(StatesGroup):
	waiting_phone = State()
	waiting_code = State()
	waiting_password = State()
