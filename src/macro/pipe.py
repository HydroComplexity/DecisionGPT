"""
"""
import pika
import json
import socket
import traceback
from time import sleep
from pika.exceptions import AMQPChannelError, AMQPConnectionError
from pika.exchange_type import ExchangeType

RMQ_IP = "rmqueue"
RMQ_PORT = 5672

class Pipe : 
	"""
	Supports dialogue between two agents.
	"""

	def __init__(self, ip_arg=RMQ_IP, port_arg=RMQ_PORT) :
		"""
		"""
		self.ip = ip_arg
		self.port = port_arg
		self.channels = ["main_q"]
		self.connection = None
		self.channel = None

	def active_listen(self, channel, method, properties, body) :
		""" Callback that activates when an agent speaks.
		"""
		obj = json.loads(body)
		self.store_message(obj)
		self.transfer_view(body)
		require_answer()

	def disconnect(self) : 
		""" Maybe useful for keeping long-running processes without mobilizing
		RabbitMQ IO.
		"""
		self.channel = None
		self.connection.close()
		self.connection = None

	def push_once(self, data_frame) :
		""" Single push of data block to a registered queue
		"""
		msg = data_frame["messages"][0]
		msg["from"] = "init"
		self.store_message(msg)
		self.transfer_view(json.dumps(msg))

		try :
			self.channel.basic_publish(exchange='queue_exchange', routing_key="",
				body=json.dumps(data_frame))

		except :
			traceback.print_exc()
			print(data_frame, flush=True)
			return False

		else :
			return True

	def reconnect(self) :
		connected = False 
		while not connected :
			try :
				self.connection = pika.BlockingConnection(
					pika.ConnectionParameters(self.ip, self.port))

			except (AMQPChannelError, AMQPConnectionError, socket.gaierror) :
				# print("Waiting to connect to queue...")
				sleep(1)

			else :
				connected = True

		self.channel = self.connection.channel()
		self.channel.exchange_declare(exchange='queue_exchange')
		self.channel.queue_declare("coord_queue")
		self.channel.queue_bind(exchange="queue_exchange", queue="coord_queue")

		self.channel.queue_declare("analysis_queue")
		self.channel.queue_bind(exchange="queue_exchange", queue="analysis_queue")

		self.channel.queue_declare("view_queue")
		self.channel.queue_declare("id_queue")
		self.channel.queue_declare("action_queue")
		self.channel.queue_declare("check_redundancy")
		self.channel.queue_declare("summarize")
		self.channel.queue_declare("gap_check")
		self.channel.queue_declare("hire_fire")
		self.channel.queue_declare("chat_comm")
