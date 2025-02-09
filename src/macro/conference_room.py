"""
"""
import os
import json
import copy
import sys
import docker
import random
import logging
import traceback
import subprocess

from macro.pipe import Pipe
from macro.backlog import Backlog, AI_Message

from time import sleep
from datetime import datetime
from dotenv import load_dotenv
from openai import AzureOpenAI
from pika import BasicProperties
from argparse import ArgumentParser

LOG_LEVEL = logging.DEBUG
load_dotenv()
# ------------------------------------------------  SETUP LOGGER

logger = logging.getLogger("agent")
logger.setLevel(LOG_LEVEL)
ch = logging.StreamHandler()
ch.setLevel(LOG_LEVEL)
formatter = logging.Formatter("{asctime}|{levelname}: {message}",
	"%H:%M:%S", style="{")
ch.setFormatter(formatter)
logger.addHandler(ch)

fh = logging.FileHandler(f"/mnt/out/logs/cr_logs/{datetime.now()}.log")
logger.addHandler(fh)


# --------------------------------------------------------------

class Conference_Room :
	"""
	"""
	def __init__(self, version_arg) : 
		"""
		"""

		self.model_name = os.getenv("OPENAI_API_DEPLOYMENT_NAME")

		self.run_number = 0
		self.add_agents = 1
		self.MIN_ASSEMBLY = 4
		self.CONVERSATION_STARTED=False
		self.MAX_INTERACTIONS_NOITER = 20
		self.MAX_INTERACTIONS = 20
		self.CHECK_FREQUENCY = 8
		self.CHECK_FREQUENCY_BASE = 8
		self.GAP_CHECK = 5
		self.ADDITIONAL = 2

		self.SUMMON_QUOTA = 5

		self.version = version_arg
		self.consumer_list = []
		self.backlog = Backlog()
		self.pipe = Pipe()

		self.profile_generation_temperature = 1.

		self.spawned_new = False

		self.client = AzureOpenAI(
			api_key=os.getenv("OPENAI_API_KEY"), 
			api_version="2023-12-01-preview",
			azure_endpoint=os.getenv("OPENAI_API_ENDPOINT")
		)

		self.pipe.reconnect()

		self.first_speaker = None
		self.first_speaker_id = None
		self.context_prompt = None
		self.first_prompt = None

		self.pipe.channel.queue_declare("id_queue")
		self.pipe.channel.queue_bind(exchange="queue_exchange", queue="hire_fire")

		self.resume_consuming()

	def analyse_assembly(self) : 
		"""
		"""
		# when a sufficient number of participants have gathered start the
		# discussion
		if len(self.backlog.agents) >= self.MIN_ASSEMBLY :
			logger.info(f"First speaker is {self.first_speaker}")
			self.start_conversation()

	def cancel_last(self) : 
		"""
		"""
		# remove lastthing of the list
		logger.debug("Rolling back last iteration...")
		try :
			self.backlog.history.pop(-1)

		except IndexError :
			# empty list
			return

		else :
			self.MAX_INTERACTIONS += 1
			self.ADDITIONAL += 1
			return

	def check_and_answer(self) : 
		"""
		"""
		self.CHECK_FREQUENCY -= 1

		if self.CHECK_FREQUENCY == 0 and self.MAX_INTERACTIONS > 0:
			self.ADDITIONAL += 1
			self.CHECK_FREQUENCY = self.CHECK_FREQUENCY_BASE

			self.check_redundancy()

			# has to return after redundancy and relevance check
			# in order to wait for another type of answer
			return


		if self.MAX_INTERACTIONS > 0 :
			self.continue_run()

		elif self.MAX_INTERACTIONS == 0 :
			self.conclude_run()

		elif self.MAX_INTERACTIONS == -1 :
			# this is over.
			self.summarize()
			logger.info("Requested summarizing message.")

		elif self.MAX_INTERACTIONS <= -2 :

			logger.debug(self.backlog.last())

			self.pipe.channel.basic_publish(exchange="", routing_key="chat_comm",
				body=json.dumps({"progress" : "stop"}))

			self.display_backlog()
			logger.info("\n\n\n")
			self.end_stats()

			while True :
				sleep(1)
			# self.pipe.channel.stop_consuming()

		self.MAX_INTERACTIONS -= 1

	def check_for_gaps(self) : 
		"""
		"""

		self.pipe.channel.basic_publish(exchange="queue_exchange",
			routing_key="gap_check", body=json.dumps(self.backlog.to_json()))

	def check_redundancy(self) :
		"""
		"""
		self.pipe.channel.basic_publish(exchange="queue_exchange",
			routing_key="check_redundancy",
			body=json.dumps(self.backlog.to_json()))

	def conclude_run(self) :
		"""
		"""
		pick = self.pick()

		backlog_copy = copy.deepcopy(self.backlog)
		backlog_copy.store_message(AI_Message(
			"The discussion must now reach a concluding statement.",
			role_arg="system", to_arg=pick))

		self.pipe.channel.basic_publish(exchange="queue_exchange",
			routing_key=f"agent_queue_{backlog_copy.agents[pick]}",
			body=json.dumps(backlog_copy.to_json()))

		logger.debug("Last conference room instruction sent.")

	def continue_run(self) : 
		"""
		"""
		pick = self.pick()
		self.send_next(pick)

	def converge(self) :
		"""
		"""
		self.gather_context()
		self.pipe.channel.start_consuming()

	def dating_app(self, profile_arg) :
		"""
		"""

		instruction_prompt = "Create a persona that fits the following profile :"

		format_prompt = """
		Summarize a simple JSON that has two properties: description and role.
		Description must be an accurate but tidy description of the profile and
		their skills. Role must be a single-word that best characterizes this
		profile. If multiple profiles are specified, select the one that fits best.
		Don't name them.
		"""
		st = datetime.now()
		response = self.client.chat.completions.create(
			model=self.model_name,
			temperature=self.profile_generation_temperature,
			messages=[
				{
					"role" : "system",
					"content" : instruction_prompt
				},
				{
					"role" : "system",
					"content" : profile_arg
				},
				{
					"role" : "system",
					"content" : format_prompt
				}		
			]
		)


		try :
			res = response.choices[0].message.content
			pass

		except (IndexError, KeyError) : 
			print(response)
			print("No answer")

		else :

			json_res = res.replace("```json", "").replace("```", "")

			try :
				res = json.loads(json_res)

			except JSONDecodeError :
				logger.error(json_res)
				logger.error("COULD NOT DECODE JSON")
				return "", None

			else :				

				res["role"] = res["role"].lower()

				logger.debug("RESULTING PROFILE #####--------")
				logger.debug(res["description"])
				print(f"Finished in {(datetime.now() - st).total_seconds()} seconds.")

				return res["description"], res["role"]

	def display_backlog(self) : 

		hist = sorted(self.backlog.history, key=lambda x: x.run)

		hist = [self.backlog.context_prompt] + hist
		for msg in hist : 
			# logger.debug("Sent backlog message in chat_comm")
			self.pipe.channel.basic_publish(exchange='', routing_key='chat_comm',
				body=json.dumps({
					"text" : msg.content,
					"stamp" : f"{msg.msg_from} | {datetime.now().strftime('%H:%M')}",
					"user_id" : msg.msg_from,
					"avatar" : f'https://robohash.org/{msg.msg_from}?bgset=set3'
				})
			)

		logger.debug(self.backlog.to_json())
		f = open(f"/mnt/out/logs/keep/{datetime.now()}.log", "w")
		f.write(str(self.backlog.to_json()))
		f.close()

	def end_stats(self) :
		"""
		"""
		stats = f"""Framework has converged. Summary of the discussion:
		Messages generated: {len(self.backlog.history)}
		Constitution of the assembly: {self.backlog.agents.keys()}
		"""
		logger.debug(stats)
		runs = []
		for msg in self.backlog.history :
			if "New agent has been summoned" in msg.content :
				runs.append(msg.run)

	def gather_context(self) : 
		"""
		"""
		self.context_prompt = open(
			f"/mnt/prompts/{self.version}/init_prompt.txt").read()
		self.context_prompt = self.context_prompt.replace("\n", " ")

	def hire_fire(self, channel, method, properties, body) : 
		"""
		"""

		logger.debug("\nRECEIVED PROFILE\n")
		try :
			analysis = json.loads(body)

		except json.JSONDecodeError :
			logger.error("THIS IS NOT JSON")

		else :
			profile = str(analysis["typical_profile"])

		desc, role = self.dating_app(profile)

	def log_conversation(self, channel, method, properties, body) :
		"""
		1st. log last generated message into the backlog
		2nd. check redundancy and relevance

		"""
		try :
			obj = json.loads(body)

		except json.JSONDecodeError :
			logger.error("##### JSON DECODE ERROR")
			logger.error(body)

			self.backlog.cancel_last()
			self.check_and_answer()

		temp_msg_list = []

		self.run_number += 1

		self.pipe.channel.basic_publish(exchange="", 
			routing_key="chat_comm",
			body=json.dumps({"progress" : self.run_number/
				(self.MAX_INTERACTIONS_NOITER + self.ADDITIONAL)}))
		logger.info(f"Iteration : {self.run_number} / " +
			f"{self.MAX_INTERACTIONS_NOITER + self.ADDITIONAL}")

		# assume the object is a list of objects, as requested to the
		# LLM driven JSON formatter
		try :
			for element in obj :
				base_obj = {
					"from_arg" : "",
					"to_arg" : "",
					"content_arg" : "",
					"role_arg" : "assistant",
					"run_arg" : self.run_number,
					"bring_in_arg" : ""
				}

				for k in element :
					try :
						base_obj[k+"_arg"] = element[k]

					except KeyError :
						pass

				temp_msg_list.append(AI_Message(
					base_obj["content_arg"],
					base_obj["from_arg"],
					base_obj["to_arg"],
					base_obj["role_arg"],
					"",
					base_obj["run_arg"],
					base_obj["bring_in_arg"]
					)
				)

		except (TypeError, IndexError) :
			# if it is not a list of messages or the JSON is not what it is expected
			# to be.
			logger.debug("Rolling back one message, conversation bug.")
			logger.debug(base_obj)
			self.backlog.cancel_last()
			self.check_and_answer()

		else :
			# logger.debug(base_obj)
			self.spawned_new = False
			if self.SUMMON_QUOTA > 0 :
				self.SUMMON_QUOTA -= 1
				for msg in temp_msg_list :
					if ((msg.bring_in != "") and (msg.bring_in not in list(self.backlog.agents.keys()))
						and (self.MAX_INTERACTIONS >= 5)):
						logger.info("A summoning request has been identified in these messages:")
						self.ADDITIONAL += 1
						self.spawned_new = True
						ndesc, nrole = self.dating_app(msg.bring_in)
						retries = 2

						while nrole in self.backlog.agents.keys() :
							if retries < 0 :
								nrole += "_2"
								break

							else :
								logger.debug("SUMMONING GENERATED A DUPLICATE AGENT, RETRYING...")
								ndesc, nrole = self.dating_app(msg.bring_in)
								retries -= 1

						self.spawn_new_agent(nrole, ndesc)
						break
				
			self.backlog.suffix_many(temp_msg_list)

		if not self.spawned_new :
			self.check_and_answer()

	def pick(self) :
		"""
		"""
		last_msg = self.backlog.last()
		if last_msg.msg_to in ["assembly", ""] :
			try :
				while ((pick := random.choice(list(self.backlog.agents.keys())))
					in [last_msg.msg_from, "moderator"]) :
					pass

			except (KeyError, IndexError) :
				logger.debug(self.backlog.agents)

			if last_msg.msg_to == "" :
				self.backlog.history[-1].msg_to = pick

		else :
			# what happens if it's not assembly nor ""
			pick = last_msg.msg_to
			try :
				self.backlog.agents[pick]

			except KeyError :
				# agent doesn't exist in the list
				# remove last message, start over
				self.backlog.cancel_last()
				pick = self.pick()

		return pick

	def receive_analysis(self, channel, method, properties, body) :
		"""
		"""
		self.backlog.analysis.append(json.loads(body))

		self.check_and_answer()
	
	def register_id(self, channel, method, properties, body) : 
		"""
		"""
		# register new agent


		obj = json.loads(body)
		logger.debug(f"Register ID was called, from {obj}")
		current_idx = len(self.backlog.agents)
		self.backlog.agents[obj["role"]] = current_idx

		# return their id so they can open a comm channel
		channel.basic_publish(
			exchange="",
			routing_key=properties.reply_to,
			properties = BasicProperties(
				correlation_id = properties.correlation_id),
			body=json.dumps({obj["role"] : current_idx}))
		channel.basic_ack(delivery_tag=method.delivery_tag)

		# open the same channel in the conference room
		self.pipe.channel.queue_declare(queue=f"agent_queue_{current_idx}")
		self.pipe.channel.queue_bind(exchange="queue_exchange",
			queue=f"agent_queue_{current_idx}")

		if not self.CONVERSATION_STARTED :
			self.reroll_first_speaker()
			self.analyse_assembly()

		if self.spawned_new :
			self.spawned_new = False

			self.backlog.history[-1].msg_to = obj["role"]

			self.check_and_answer()

	def reroll_first_speaker(self) : 
		"""
		"""
		while ((tmp_first_speaker := random.choice(list(self.backlog.agents.keys() )))
			== "moderator" and len(self.backlog.agents) > 1 ):
			pass

		self.first_speaker = tmp_first_speaker

		try :
			self.first_speaker_id = self.backlog.agents[self.first_speaker]

		except (IndexError, KeyError) :
			logger.error(self.backlog.agents)

	def resume_consuming(self) :
		"""
		"""
		self.consumer_list.append(self.pipe.channel.basic_consume(queue="id_queue",
			on_message_callback=self.register_id))

		self.consumer_list.append(self.pipe.channel.basic_consume(queue="coord_queue",
		 on_message_callback=self.log_conversation))

		self.consumer_list.append(self.pipe.channel.basic_consume(queue="analysis_queue",
			on_message_callback=self.receive_analysis))

		# resume
		pass

	def send_next(self, pick_arg) :
		"""
		chlog: removed try_catch in case pick was not in agent, 
		is now handled in self.pick
		"""
		self.pipe.channel.basic_publish(exchange="queue_exchange",
			routing_key=f"agent_queue_{self.backlog.agents[pick_arg]}", 
			body=json.dumps(self.backlog.to_json()))

	def spawn_new_agent(self, role_arg, persona_prompt) :
		"""
		"""
		logger.debug("##### ENTERING SPAWN FUNCTION")

		client = docker.from_env()

		try :
			client.services.create(
				image="python_gpt2",
				command=f'python /mnt/src/micro/agent.py --role custom --rolename "{role_arg}" --prompt "{persona_prompt}"',
				env=["PYTHONPATH=/mnt/src"],
				name=f"add_agent{self.add_agents}",
				mounts=["/Users/adt5/Desktop/Sprint2/DecisionGPT:/mnt"],
				networks=["decisiongpt_gptnet"]
			)

		except docker.errors.APIError :
			self.add_agents += 1
			self.spawn_new_agent(role_arg, persona_prompt)

		else :
			self.add_agents += 1
			self.run_number += 1
			self.backlog.suffix_many([
				AI_Message(f"New agent has been summoned: {role_arg}", "system", "",
					"system", "", self.run_number, "")
			])

	def start_conversation(self) : 
		"""
		Send the context message to agents in order to start the conversation.
		"""
		logger.info("Minimum assembly is gathered, starting conversation.")
		fprompt = AI_Message(self.context_prompt, from_arg="moderator", 
			to_arg=self.first_speaker, role_arg="system")

		self.backlog.set_context_prompt(fprompt)

		self.pipe.channel.basic_publish(exchange="queue_exchange",
			routing_key=f"agent_queue_{self.first_speaker_id}",
			body=json.dumps(self.backlog.to_json()))

		logger.info(self.backlog.agents)
		logger.info("Init message sent.")

		self.CONVERSATION_STARTED = True

	def summarize(self) : 
		"""
		"""
		self.pipe.channel.basic_publish(exchange="", routing_key="summarize",
			body=json.dumps(self.backlog.to_json()))

	def wait_for_id(self) :
		"""
		"""
		self.pipe.channel.stop_consuming()

		for c in self.consumer_list() :
			self.pipe.channel.basic_cancel(c)

		self.consumer_list.append(self.pipe.channel.basic_consume(queue="id_queue",
			on_message_callback=self.register_id))

		self.pipe.channel.start_consuming()


if __name__ == "__main__" :
	parser = ArgumentParser()
	parser.add_argument("--use", type=str)

	args = parser.parse_args()

	conference_room = Conference_Room(args.use)
	conference_room.converge()
