import json
import time
import pika

from pika.exceptions import AMQPChannelError, AMQPConnectionError

class GPTQueue :
	def __init__(self, addr_arg) :
		"""
		"""
		self.addr = addr_arg
		self.connection = None
		self.channel = None
		self.queue = None
		self.exec_over = False

	def signal_download_ready(self, filepath_arg) :
		"""
		"""
		self.channel.basic_publish(
			exchange="",
			body=json.dumps({
				"action" : "download_ready",
				"filepath" : filepath_arg
			}),
			routing_key="action_queue"
		)

	def publish_loop(self, shared_list) :
		"""
		"""
		while not self.exec_over :
			try :
				new_message = shared_list.pop(0)

			except IndexError :
				pass

			else :
				try :
					message_obj = json.loads(new_message)
					command = message_obj["command"]

				except (KeyError, json.JSONDecodeError) :
					# if command not in the object
					self.queue_message_wrapper(new_message)

				else :
					if command == "download_ready" :
						self.signal_download_ready(message_obj["payload"])

					if command == "shutdown" :
						self.exec_over = True

			time.sleep(.3)

	def wait_for_frontend_signal(self) :
		"""
		"""
		self.channel.queue_declare("start_queue")
		gogo = False
		while not gogo :
			method, properties, body = self.channel.basic_get("start_queue")

			try :
				received_prompt = body.decode("utf-8")
				print(received_prompt, flush=True)

			except AttributeError :
				time.sleep(.5)

			else :
				received_prompt = json.loads(received_prompt)
				gogo = True

		return received_prompt

	def queue_message_wrapper(self, message) :
		"""
		"""
		self.channel.basic_publish(exchange="", 
			body=message, routing_key="work_queue")

	def connect(self) :
		"""
		"""
		connected = False

		while not connected :
			try :
				self.connection = pika.BlockingConnection(
					pika.URLParameters(self.addr))
				self.channel = self.connection.channel()
				self.channel.queue_declare(queue="work_queue")
				self.channel.queue_declare("action_queue")

			except (AMQPConnectionError, AMQPChannelError) :
				print("Still attempting to connect to RMQ...", flush=True)
				time.sleep(2)

			else :
				connected = True

		print("Connect to rmq, queue opened.", flush=True)

