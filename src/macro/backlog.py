"""
"""
import json
import secrets

color_list = ["indigo"]

class Backlog :
	"""
	Storage for agent-genereated messages.
	"""

	def __init__(self) :
		"""
		"""
		self.history = []
		self.analysis = []
		self.agents = {}
		self.context_prompt = None

	def __repr__(self) :
		"""
		"""
		return "Backlog()"

	def __str__(self) :
		"""
		"""
		return ("Context settings :\n------------------------------\n\n" +
			f"{self.context_prompt}" + "\n\n" +
			"\n\n".join([x.__str__() for x in self.history]) +
			"\n\nAnalysis outputs: \n------------------------------\n" + 
			"\n".join([json.dumps(x) for x in self.analysis]) 
			+ "\n-------------------------------\n" +
			f"Agents: {', '.join(list(self.agents.keys()))}")

	@classmethod
	def from_json(cls, json_payload) :
		"""
		From text-unpacked JSON
		"""
		new_obj = cls()
		new_obj.agents = json_payload["agents"]
		new_obj.context_prompt = AI_Message.from_json(
			json_payload["context_prompt"])

		for m in json_payload["messages"] :
			new_obj.history.append(AI_Message.from_json(m))

		return new_obj

	def cancel_last(self) :
		"""
		"""
		try :
			self.history.pop(-1)

		except IndexError :
			pass

	def get_agents(self) :
		"""
		"""
		return self.agents

	def history_openai(self) :
		history_copy = []

		for x in self.history :
			if x.msg_from != "system" :
				history_copy.append(x)

		return history_copy

	def last(self) :
		"""
		"""
		try :
			return self.history[-1]
		except IndexError :
			return AI_Message(
				self.context_prompt, "system", "assembly", "user", "", "", "")

	def openai_format(self) :
		"""
		"""
		return [
			x.to_openai() for x in self.history
		]

	def prefix_many(self, payload) :
		"""
		"""
		self.history = payload + self.history

	def set_context_prompt(self, new_context_prompt) :
		"""
		"""
		self.context_prompt = new_context_prompt

	def store_message(self, msg_obj) :
		"""
		"""
		self.history.append(msg_obj)


	def suffix_many(self, payload) :
		"""
		"""
		self.history += payload

	def to_json(self) :
		"""
		"""
		return {
			"agents" : self.agents,
			"messages" : [x.to_json() for x in self.history],
			"context_prompt" : self.context_prompt.to_json()
		}


class AI_Message :
	"""
	Allows easy transformation of messages to fit AI and HID purposed
	"""

	def __init__(self, content_arg, from_arg="", to_arg="", role_arg="assistant",
		uuid=None, run_arg=0, bring_in_arg="") :
		"""
		"""
		self.uuid = secrets.token_hex(16)

		self.content = content_arg
		self.msg_from = from_arg
		self.msg_to = to_arg

		self.role = role_arg
		self.run = run_arg

		self.bring_in = bring_in_arg

	def __repr__(self) :
		"""
		"""
		return self.__str__()

	def __str__(self) :
		"""
		"""
		return f"""From: {self.msg_from},
							 To: {self.msg_to} (run: {self.run})
		-----------------------

		{self.content}

		-----------------------
		Bring in:
		{self.bring_in}

		"""

	@classmethod
	def from_json(cls, json_payload) :
		"""
		JSON deserializer
		"""
		return cls(
			json_payload["content"],
			json_payload["msg_from"],
			json_payload["msg_to"],
			json_payload["role"],
			json_payload["uuid"],
			json_payload["run"],
			json_payload["bring_in"]
		)

	def set_from(self, new_from) :
		"""
		"""
		self.msg_from = new_from

	def set_to(self, new_to) :
		"""
		"""
		self.msg_to = new_to

	def to_framework(self) :
		"""
		"""
		return {
			"from" : self.msg_from,
			"to" : self.msg_to,
			"message" : self.content
		}

	def to_json(self) :
		"""
		JSON serializable
		"""
		return {
			"content" : self.content,
			"msg_from" : self.msg_from,
			"msg_to" : self.msg_to,
			"role" : self.role,
			"uuid" : self.uuid,
			"run" : self.run,
			"bring_in" : self.bring_in
		}

	def to_openai(self) :
		return {
			"role" : self.role,
			"content" : f"Message from {self.msg_from}: " + self.content
		}

	def to_openai_json(self) :
		return {
			"role" : self.role,
			"content" : self.content
		}
