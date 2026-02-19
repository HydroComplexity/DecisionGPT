import os
import ast
import pika
import json
import asyncio
import reflex as rx
from typing import List, TypedDict
import pprint

from frontend.states.prompt_state import PromptState
from frontend.states.prompt_state import InitPromptText, MayorPromptText
from frontend.states.prompt_state import ScientistPromptText, AdvocatePromptText


prompt_box_roles = {
	"init" : InitPromptText,
	"mayor" : MayorPromptText,
	"scientist" : ScientistPromptText,
	"advocate" : AdvocatePromptText,
}

RABBITMQ_HOST = "queue"
# RABBITMQ_HOST = "localhost"
RABBITMQ_QUEUE = "work_queue"
RABBITMQ_ACTION_QUEUE = "action_queue"

def create_unique_filename(file_name: str) :
	import random
	import string

	filename = "".join(
		random.choices(
			string.ascii_letters + string.digits, k=10
			)
		)
	return filename + "_" + file_name


class Message(TypedDict):
	text: str
	message_type: str
	is_user: bool
	sender: str

class ChatState(rx.State):
	messages: List[Message] = []
	messages_raw: List[dict]= []
	file: str								= ""
	download_data: str			= ""

	@rx.event
	def add_received_message(
		self, text: str, message_type_arg: str, sender_arg: str):
		"""Internal event to add messages from MQ to the state's message list."""
		self.messages.append(
			Message(
				text=text,
				is_user=False,
				message_type=message_type_arg,
				sender=sender_arg
			)
		)

	@rx.event
	async def handle_upload(
		self, files: list[rx.UploadFile]) :
		"""
		"""
		for file in files :
			upload_data = await file.read()
			upload_content = upload_data.decode()
			loaded = json.loads(upload_content)

			self.messages = []

			for msg in loaded :
				text, message_type, sender = self.unpack_message(msg)

				if text is not None and message_type is not None :
					self.add_received_message(text, message_type, sender)

	@rx.event
	async def handle_download(self) :
		return rx.download(
			data = json.dumps(self.messages_raw),
			filename="conversation.log"
		)

	@rx.event
	async def set_ready(self, message_body) :
		"""
		"""
		message_body = {}

		for role in prompt_box_roles :
			prompt_text = await self.get_state(prompt_box_roles[role])
			message_body[f"{role}_prompt_arg"] = prompt_text.text


		conn, chan = await self.connect(special_message="send")
		chan.queue_declare(queue="start_queue")

		chan.basic_publish(exchange="", body = json.dumps(message_body),
			routing_key="start_queue")

		conn = False
		chan = False

		self.start_messages(button_action=True)

		return

	def start_messages(self, button_action=False) :
		self.messages = []
		self.messages.append(
			Message(
				text="Padding message.",
				is_user=False,
				sender="padding"
			)
		)

		self.messages.append(
			Message(
				text="Padding message.",
				is_user=False,
				sender="padding"
			)
		)

		if button_action :
			self.messages.append(
				Message(
					text="App online. Starting framework...",
					is_user=False,
					sender="system"
				)
			)

		else :
			self.messages.append(
				Message(
					text="App online. Ready to start.",
					is_user=False,
					sender="system"
				)
			)


	@rx.event
	async def connect(self, special_message=None) :
		"""
		"""
		parameters = pika.ConnectionParameters(
			RABBITMQ_HOST
		)
		connection = pika.BlockingConnection(parameters)
		channel = connection.channel()
		channel.queue_declare(
			queue=RABBITMQ_QUEUE
		)
		channel.queue_declare(
			queue=RABBITMQ_ACTION_QUEUE
		)

		if not special_message :
			async with self:
				self.start_messages()

		return connection, channel


	def process_markdown_hsic(self, content) :
		"""
		"""
		result = content["function_response"]["response"]["result"]

		if content["function_response"]["name"] == "get_river_height" :
			ret_message = f"River height: {result}"
			ret_sender = "get_river_height"
			ret_type = "interaction"

		else :
			ret_message = "| Input Prompt | Subtask | HSIC | Cossimilarity | \n"
			ret_message += "| ---- | ---- | ---- | ---- | \n "
			for res in result : 
				ret_message += f"| Input Prompt | {res['input_2']} | {res['hsic']:.4f} | {res['cosine']:.4f} | \n"

			ret_type = "markdown"
			ret_sender = content["function_response"]["name"]

		return ret_message, ret_type, ret_sender


	def process_decision_message(self, ret_message) :
		"""
		"""
		if ret_message["decision"] :
			decision = "<b>satisfactory</b>"

		else :
			decision = "<b>unsatisfactory</b>"


		if "justification" in ret_message :
			justifications = ret_message['justification']

		else :
			justifications = ret_message['justifications']

		ret_message = f"""The evaluator agent find the analysis {decision}.
		Reasons are: {justifications}
		"""
		ret_type = "interaction"
		ret_sender = "disaster_agent"

		return ret_message, ret_type, ret_sender


	def unpack_message(self, json_message) :
		"""
		"""
		FAIL = '\033[91m'
		ENDC = '\033[0m'

		try :
			json_message = json_message.decode()

		except ValueError :
			print("Decoding error: ", json_message)

		except AttributeError :
			pass


		ret_message = None
		ret_type = None
		ret_sender = "system"

		message = json.loads(json_message)

		# pprint.pp(message, indent=2)
		# print("\n\n", flush=True)

		try :
			content = message["content"]["parts"][0]

		except KeyError :
			# print(message, flush=True)
			pass

		except TypeError :
			pass

		except IndexError :
			# message has no parts, so likely it is an action?
			return None, None, None

		else :
			if "function_response" in content and content["function_response"] :
				# this is the transfer case
				# this should be treated as fineprint
				try :
					transferee = message["actions"]["transfer_to_agent"]
	
				except KeyError :

					try :
						summon_type = content["function_response"]["response"]["agent_profile"]
						summon_desc = content["function_response"]["response"]["agent_description"]
						ret_message = f"Trying to summon an {summon_type} agent with description: {summon_desc}."
						ret_type = "summon"

					except KeyError :
						try :
							ret_message, ret_type, ret_sender = self.process_markdown_hsic(content)

						except KeyError :
							try :
								decision = (
									content["function_response"]["response"]["decision"] == "True")
								justification = content["function_response"]["response"]["justification"]

							except KeyError :
								print(FAIL + f"[DEBUG] {content}" + ENDC, flush=True)

							else :
								return None, None, None

						else :
							pass

				else :
					# print(message, flush=True)
					if message["actions"]["transfer_to_agent"] :
						ret_type = "transfer"
						ret_message = f"Speaking token transferred to {transferee}"

					else :

						try :
							ret_message, ret_type, ret_sender = self.process_markdown_hsic(content)

						except KeyError :

							try :
								summon_type = content["function_response"]["response"]["agent_profile"]
								summon_desc = content["function_response"]["response"]["agent_description"]
								ret_message = f"Trying to summon an {summon_type} agent with description: {summon_desc}."
								ret_type = "summon"

							except KeyError :
								try :
									ret_message, ret_type, ret_sender = self.process_decision_message(message)

								except (KeyError, TypeError) :
									print(ret_message)

				
			elif "function_call" in content  and content["function_call"]:
				# ignore, there are too much of these and they carry no info
				pass

			else :
				# technically, if a message reached here, it's text

				try :
					ret_message = content["text"]

				except KeyError :
					return None, None, None

				else :
					if "[SKIP]" in ret_message :
						if message["author"] == "summarizer_agent" :
							return None, None, None

						elif message["author"] == "summoner_agent" :
							return ret_message.split("[SKIP] ")[-1], "transfer", "system"

						elif message["author"] == "disaster_agent" :
							return ret_message.split("[SKIP] ")[-1], "transfer", "system"

					elif message["author"] == "disaster_agent" :
						ret_message = json.loads(ret_message)
						ret_message, ret_type, ret_sender = self.process_decision_message(ret_message)

					elif ret_message == "" :
						return None, None, None


				ret_type = "interaction"
				ret_sender = message["author"]

		return ret_message, ret_type, ret_sender

	@rx.event(background=True)
	async def rabbitmq_consumer_loop(self):
		try:
			connection, channel = await self.connect()
			while True:
				try :
					# regular message channel

					method_frame, properties, body = (
						channel.basic_get(
							RABBITMQ_QUEUE, auto_ack=False
						)
					)
					if method_frame:
						async with self :
							text, message_type, sender = self.unpack_message(body)

							if text is not None and message_type is not None :

								self.messages_raw.append(body.decode("utf-8"))

								yield self.add_received_message(
									text, message_type, sender
								)
								channel.basic_ack(
									method_frame.delivery_tag
								)
					else:
						await asyncio.sleep(0.3)

					method_frame, properties, body = (
						channel.basic_get(
							RABBITMQ_ACTION_QUEUE,
							auto_ack=False
						)
					)
					if method_frame :
						async with self :
							print(method_frame, properties, body, flush=True)
							received_msg = json.loads(body)
							action_type = received_msg["action"]
							print(action_type, flush=True)

							if action_type == "download_ready" :
								self.download_data = json.dumps(received_msg["payload"])

				except pika.exceptions.StreamLostError:
					async with self:
						self.messages.append(
							Message(
								text="RabbitMQ connection lost. Attempting to reconnect...",
								is_user=False,
							)
						)

				await asyncio.sleep(0.1)

		except (
			pika.exceptions.AMQPConnectionError,
			pika.exceptions.StreamLostError,
		) as e:
			error_msg = (
				f"RabbitMQ Connection/Stream Error: {e}"
			)
			print(error_msg, flush=True)


	@rx.event
	def initial_connect(self):
		return ChatState.rabbitmq_consumer_loop
		# return rx.noop()