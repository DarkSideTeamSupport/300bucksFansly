from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional
import uuid

from web.services.export_options import ExportOptions
from web.services.proxy import ProxySettings


class AuthStep(str, Enum):
	PHONE = "phone"
	CODE = "code"
	PASSWORD = "password"
	QR = "qr"
	DONE = "done"
	ERROR = "error"


@dataclass
class LoginState:
	login_id: str
	step: AuthStep = AuthStep.PHONE
	phone: Optional[str] = None
	session_path: Optional[str] = None
	client: Any = None
	phone_code_hash: Optional[str] = None
	error: Optional[str] = None
	user_label: Optional[str] = None
	user_id: Optional[int] = None
	username: Optional[str] = None
	export_dir: Optional[str] = None
	job_id: Optional[str] = None
	proxy: Optional[ProxySettings] = None
	options: ExportOptions = field(default_factory=ExportOptions)
	cloud_password: Optional[str] = None
	qr_login: Any = None
	qr_url: Optional[str] = None
	qr_svg: Optional[str] = None
	qr_expires: Optional[str] = None
	# device_model / system_version / app_version с браузера посетителя
	device_params: Optional[dict] = None


class LoginStore:
	"""Хранилище незавершённых веб-логинов в памяти процесса."""

	def __init__(self) -> None:
		self._items: Dict[str, LoginState] = {}

	def create(self) -> LoginState:
		login_id = uuid.uuid4().hex
		state = LoginState(login_id=login_id)
		self._items[login_id] = state
		return state

	def get(self, login_id: str) -> Optional[LoginState]:
		return self._items.get(login_id)

	def remove(self, login_id: str) -> None:
		self._items.pop(login_id, None)


login_store = LoginStore()
