"""
"""
import os
import time
import json
import logging
import traceback

from macro.pipe import Pipe
from macro.backlog import AI_Message, Backlog

from dotenv import load_dotenv
from datetime import datetime
from openai import AzureOpenAI
from pika import BasicProperties
from argparse import ArgumentParser
from pika.exceptions import ChannelClosedByBroker

LOG_LEVEL = logging.DEBUG
load_dotenv()
# ------------------------------------------------  SETUP LOGGER

logger = logging.getLogger("agent")
logger.setLevel(LOG_LEVEL)
ch = logging.StreamHandler()
ch.setLevel(LOG_LEVEL)
formatter = logging.Formatter("{levelname}: {message}",
	"%H:%M:%S", style="{")
ch.setFormatter(formatter)
logger.addHandler(ch)

fh = logging.FileHandler(f"/mnt/out/logs/agent_logs/{datetime.now()}.log")
logger.addHandler(fh)
# --------------------------------------------------------------

class Agent :
	"""
	"""
	def __init__(self, role_arg, use_version_arg, prompt_arg, role_name) :
		"""
		"""

		self.model_name = os.getenv("OPENAI_API_DEPLOYMENT_NAME")

		self.moderation_temperature = .7
		self.core_discussion_temperature = .7
		self.json_generation_temperature = .3
		self.summary_temperature = .3

		if use_version_arg is not None :
			self.use_version = use_version_arg

		if role_arg == "custom" :
			self.role = role_name
			self.character = prompt_arg

		else :
			self.role = role_arg
			self.character = open(
				f"/mnt/prompts/{self.use_version}/{self.role}_prompt.txt").read()

		logger.debug(f"Hi I am a new agent and I just popped up as {self.role}.")

		self.character = AI_Message(self.character, role_arg="system")
		logger.info(self.character)

		self.context_just_once = True

		self.client = AzureOpenAI(
			api_key=os.getenv("OPENAI_API_KEY"), 
			api_version="2023-12-01-preview",
			azure_endpoint=os.getenv("OPENAI_API_ENDPOINT")
		)

		self.pipe = Pipe()
		self.pipe.reconnect()

		logger.debug("Connected to RMQ.")

		if self.role == "moderator" :
			self.pipe.channel.queue_bind(exchange="queue_exchange",
				queue="check_redundancy")

			self.pipe.channel.basic_consume(queue="check_redundancy",
				on_message_callback=self.check_for_redundancy)

			self.pipe.channel.basic_consume(queue="summarize", 
				on_message_callback=self.summarize_conversation)

			self.pipe.channel.queue_bind(exchange="queue_exchange",
				queue="gap_check")

			self.pipe.channel.basic_consume(queue="gap_check",
				on_message_callback=self.analyze_knowledge_gaps)

		logger.info(f"Agent {args.role} connected.")

		self.corr_id = None

		self.identify()

		#### PROMPT SEQUENCE ---------------------

		self.assembly_comp = """
		You are in a conference room with %s in order to address
		an imminent challenge."""

		self.instructions_prompt = [
			"""
			Participants must be referred to with their role, one at a time.
			Don't use markdown syntax and keep the answer under 100 words.
			Closely follow instructions from the moderator. Do not reintroduce
			yourself at every interaction using "as the ...".
			"""
		]

		self.req_for_help_prompt = """
		You are able to summon external help.
		Be precise, and explicitely request the needed expert profile.
		"""

		self.talking_prompt = f"{self.role}: "

		self.json_instructions = f"""
		Extract features from this message corresponding to JSON properties from,
		to, content. from must be set to {self.role}. Precisely indentify the
		interlocutor and set the property to. If the message is a general comment,
		or you cannot identify an interlocutor, to must be set to assembly. Also
		include a property named bring_in. If you identify an explicit request for
		another expert formulated by an agent, and is not yet in the conference
		room, set bring_in accordingly. Otherwise, set it to empty string.
		Lowercase only. The result must be a list of JSON objects."""

	def analyze_knowledge_gaps(self, channel, method, properties, body) :
		"""
		"""
		
		blobj = Backlog.from_json(json.loads(body))

		instructions_prompt = """
		Create a JSON object that contains three properties: solution_list,
		best_solution, and typical_profile.
		solution_list contains the solutions to the problem, without description.
		best_solution contains the solution that represents the most beneficial
		contribution to the problem.
		typical_profile represents a profile, not present in the room, that is able
		to realize or improve this solution.

		"""

		blobj.suffix_many([self.character])
		blobj.suffix_many([AI_Message(instructions_prompt, role_arg="system")])

		logger.debug("OpenAI: Looking for knowledge gap.")
		response = self.client.chat.completions.create(
			model=self.model_name,
			temperature=.7,
			messages=blobj.openai_format(),
			max_tokens=300
		)

		try :
			res = response.choices[0].message.content

		except (IndexError, KeyError) :
			pass
			logger.error(response)

		else :
			logger.debug("\n################################################")
			logger.debug(res)
			res2 = res.replace("```json", "").replace("```", "")

			self.pipe.channel.basic_publish(exchange="queue_exchange",
				routing_key="hire_fire", body=res2)

	def answer_callback(self, channel, method, properties, body) :
		"""
		Processes messages of type JSON-serialized Backlog
		"""
		messages = Backlog.from_json(json.loads(body))
		try : 
			last_message = messages.last()
			if last_message.msg_to in [str(self.role), "assembly"] :
				logger.debug(f"{self.role} received the message!")

			else :
				logger.debug("That message was not intended for me.")
				return

		except IndexError :
			if messages.context_prompt.msg_to == str(self.role) :
				logger.debug(f"{self.role} received the message!")

			else :
				return

		response = self.construct_answer(messages)
		self.json_send(response)

	def check_for_redundancy(self, channel, method, properties, body) :
		"""
		"""
		logger.info("Received request for relevance and redundancy check.")
		messages = Backlog.from_json(json.loads(body))

		prompt = """
		Create a summary of the discussion and determine whether the discussion is
		progressing towards resolution or not. If discourse is not progressing,
		provide refined guidance based on the summary and guide the participants
		towards unexplored challenges. Adapt your analysis based on your previous
		analysis, and participants' profiles and provide more nuanced and refined
		guidance for every interaction. Do not repeat arguments from previous
		analyses. Avoid repetitions of previous moderator messages at all cost.
		You can determine if the conversation is not adding new insights and
		terminate the discussion. Answer using JSON where the "analysis" property
		contains your analysis addressed at the assembly, and the property
		"decision" contains yes or no depending on the need to refocus
		the debate. Don't nest JSON structures. Produce creative writing so that
		the analysis is tailored to the current state of the conversation.		
		"""

		messages.history = (
			[x for x in messages.history if x.msg_from == "moderator"]
			+ messages.history[-10:])

		logger.debug(messages)

		messages.suffix_many([self.character])
		messages.suffix_many([AI_Message(prompt, role_arg="system")])

		logger.debug("OpenAI: Redundancy and relevance check prompt call.")
		response = self.client.chat.completions.create(
			model=self.model_name,
			temperature=self.moderation_temperature,
			messages=messages.openai_format(),
			max_tokens=4096
		)

		try :
			res = response.choices[0].message.content
			res_obj = json.loads(res)

			logger.debug(res_obj)

		except (IndexError, KeyError) :
			pass
			logger.error(response)

		except ValueError : # integrates JSONDecodeError that inherits from it
			pass
			# traceback.print_exc()
			logger.error("JSON mismatch, fixing...")
			logger.error(res)
			res_obj = json.loads(res.replace("```json", "").replace("```", ""))

		else :
			logger.debug(res_obj)

		if res_obj["decision"] == "yes" :
			msg_base = {}
			msg_base["content"] = ""

			try : 
				msg_base["content"] += res_obj["analysis"]

			except TypeError :
				msg_base["content"] += json.dumps(res_obj["analysis"])

			msg_base["from"] = self.role
			msg_base["to"] = "assembly"

			self.pipe.channel.basic_publish(exchange="queue_exchange",
				routing_key="coord_queue", body=json.dumps([msg_base]))

		elif res_obj["decision"] == "no" :
			self.pipe.channel.basic_publish(exchange="queue_exchange",
				routing_key="analysis_queue", body=json.dumps(res_obj["analysis"]))

		else :
			logger.error("Incorrect decision in moderator JSON.")


	def construct_answer(self, msgs) :
		""" Builds an answer based on the list of previous messages
		in the conversation, passed as a Backlog objet.
		"""

		local_msg = []
		ag_list = []

		logger.debug(msgs.history_openai())
		logger.debug(msgs.openai_format())

		for agit in msgs.agents.keys() :
			if agit not in ["moderator", self.role] :
				ag_list.append(agit)

		local_msg.append(
			AI_Message(self.assembly_comp % " and a ".join(ag_list),
			role_arg="system"))

		# insert context just once and see what it does.
		if self.context_just_once :
			local_msg.append(msgs.context_prompt) # init prompt loaded from text file

		for inst in self.instructions_prompt :
			local_msg.append(AI_Message(inst, role_arg="system"))

		local_msg.append(AI_Message(self.req_for_help_prompt, role_arg="system"))
		msgs.prefix_many(local_msg)

		msgs.suffix_many([self.character, AI_Message(self.talking_prompt,
			role_arg="system")])

		logger.debug("OpenAI: Core discussion prompt call.")

		response = self.client.chat.completions.create(
			model=self.model_name,
			temperature=self.core_discussion_temperature,
			messages=msgs.openai_format(),
			max_tokens=4096)

		try :
			response = response.choices[0].message.content

		except (KeyError, IndexError) :
			logger.error("An error occured while interacting with OPENAI")
			traceback.print_exc()

		else :
			return self.smart_json_formatter(response)


	def identify(self) :
		"""
		"""
		frame = {"role" : self.role}
		pframe = json.dumps(frame)

		res = self.pipe.channel.queue_declare(queue="", exclusive=True)
		self.callback_q = res.method.queue
		self.pipe.channel.basic_consume(self.callback_q,
			on_message_callback=self.open_agent_queue_2)

		self.pipe.channel.basic_publish(
			exchange="",
			routing_key="id_queue",
			properties=BasicProperties(
				reply_to=self.callback_q,
				correlation_id = self.corr_id
				),
			body = pframe)
		logger.info("Just sent my ID!")


	def json_send(self, payload) :
		"""
		"""
		logger.debug(f"PAYLOAD TO BE SENT BY AGENT {self.role}")
		logger.debug(payload)
		self.pipe.channel.basic_publish(exchange="", routing_key="coord_queue",
			body=payload)

		try :
			pobj = json.loads(payload)[0]

		except (json.JSONDecodeError, IndexError, TypeError) :
			pass

		else :
			try :
				chat_message = {
					"text" : pobj["content"],
					"stamp" : f'{pobj["from"]} - {datetime.now()}',
					"user_id" : pobj["from"],
					"avatar" : f'https://robohash.org/{pobj["from"]}?bgset=set3'
				}

			except KeyError :
				logger.error("Argh there is a JSON property that was not generated...")

			else :
				logger.info("########### WOAW, message was sent to chat_comm")

	def open_agent_queue_2(self, channel, method, properties, body) :
		"""
		"""
		data = json.loads(body)
		intid = int(data[self.role])

		res = self.pipe.channel.queue_declare(queue=f"agent_queue_{intid}")

		self.agent_queue = res.method.queue
		self.pipe.channel.queue_bind(exchange="queue_exchange",
			queue=self.agent_queue)

		self.pipe.channel.basic_consume(queue=self.agent_queue, 
			on_message_callback=self.answer_callback)

		logger.info("Personal queue opened.")

	def run(self) :
		self.pipe.channel.start_consuming()

	def send(self, message) :
		"""
		"""
		obj = AI_Message(message, from_arg=self.role, to_arg="",
			role_arg="assistant")
		
		self.pipe.channel.basic_publish(exchange="", routing_key="coord_queue",
			body = json.dumps(obj.to_json()))



	def smart_json_formatter(self, input_text) :
		"""
		"""
		st = datetime.now()
		tmp_backlog = Backlog()
		instructions = AI_Message(self.json_instructions, role_arg="system")

		tmp_response = AI_Message(input_text)
		tmp_backlog.prefix_many([instructions, tmp_response])

		logger.debug("OpenAI: JSON format prompt call.")

		json_response = self.client.chat.completions.create(
			model=self.model_name,
			temperature=self.json_generation_temperature,
			messages=tmp_backlog.openai_format(),
			max_tokens=4096
		)

		try :
			json_response = json_response.choices[0].message.content

		except (KeyError, IndexError) :
			logger.error("An error occured while calling OpenAI API.")
			traceback.print_exc()

		else :
			json_response = json_response.replace("```json", "").replace("```", "")
			return json_response

	def summarize_conversation(self, channel, method, properties, body) :
		"""
		"""
		blog = Backlog.from_json(json.loads(body))
		
		sum_prompt = """
		Summarize this conversation into a sensible report that clearly highlights
		tasks and analysis. Separate agents that were here from the beginning, and
		those who have been summoned during the conversation.
		Explicitely list advantages and drawbacks of every
		solution, using ASCII bullet points. DO NOT use markdown syntax.
		"""

		instructions = [
			AI_Message(sum_prompt, role_arg="system"),
			AI_Message("Agents here from the beginning: mayor, spokesperson, "
				+ "scientist, moderator.", role_arg="system")
		]
		blog.suffix_many(instructions)

		logger.debug("OpenAI: Summarizing prompt call.")

		summary = self.client.chat.completions.create(
			model=self.model_name,
			temperature=self.summary_temperature, 
			messages=blog.openai_format(),
			max_tokens=4096
		)

		try :
			summary_response = summary.choices[0].message.content

		except (KeyError, IndexError) :
			logger.error("An error occurred while calling OpenAI APIs.")
			traceback.print_exc()

			summary_response = ""

		self.pipe.channel.basic_publish(exchange="", routing_key="coord_queue",
			body = json.dumps([
				{"content" : summary_response, "from" : "summarizer", "to" : ""}]))


if __name__ == "__main__" :
	parser = ArgumentParser()
	parser.add_argument("--role", type=str)
	parser.add_argument("--use", type=str)
	parser.add_argument("--prompt", type=str)
	parser.add_argument("--rolename", type=str)

	args = parser.parse_args()
	ag = Agent(args.role, args.use, args.prompt, args.rolename)

	ag.run()
