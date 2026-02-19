from frontend.states.prompt_state import load_prompt

class PromptStateGenAI :
	"""
	"""
	init_prompt: str = load_prompt("init_prompt_v2")

	common_instructions: str = open(
		"prompts/common_instructions.txt").read()

	commoner_summon_instructions: str = open(
		"prompts/commoner_summon_instructions.txt").read()

	summoner_agent_instructions: str = open(
		"prompts/summoner_agent_instructions.txt").read()

	mayor_prompt: str = open("prompts/mayor.txt").read()
	scientist_prompt: str = open("prompts/scientist.txt").read()
	advocate_prompt: str = open("prompts/advocate.txt").read()
	disaster_prompt: str = open("prompts/disaster.txt").read()

	moderator_instructions = open("prompts/moderator.txt").read()

	# mayor_description: str = open("prompts/mayor_description.txt").read()

	summarizer_prompt = """Read from the context and/or state in order to summarize
	the conversation driven by your fellow agents. Enunciate the solutions
	envisioned, and outline a plan in order to achieve those solutions.
	Use Markdown to format Include the number of messages sent by every agent,
	excluding summoner_agent, disaster_agent, hsic_agent and task_breaker_agent.
	"""

	def replace_all(self, init_prompt_arg, common_instructions_arg, 
		commoner_summon_instructions_arg, summoner_agent_instructions_arg,
		mayor_prompt_arg, scientist_prompt_arg, advocate_prompt_arg,
		disaster_prompt_arg, moderator_instructions_arg) :

		self.init_prompt = init_prompt_arg
		self.common_instructions = common_instructions_arg
		self.commoner_summon_instructions = commoner_summon_instructions_arg
		self.summoner_agent_instructions = summoner_agent_instructions_arg

		self.mayor_prompt = mayor_prompt_arg
		self.scientist_prompt = scientist_prompt_arg
		self.advocate_prompt = advocate_prompt_arg
		self.disaster_prompt = disaster_prompt_arg
		self.moderator_instructions = moderator_instructions_arg

	def replace_modifiable_prompts(self, init_prompt_arg, mayor_prompt_arg,
		scientist_prompt_arg, advocate_prompt_arg) :
		"""
		"""
		self.init_prompt = init_prompt_arg
		self.mayor_prompt = mayor_prompt_arg
		self.scientist_prompt = scientist_prompt_arg
		self.advocate_prompt = advocate_prompt_arg

	def replace_init_prompt(self, init_prompt_arg) :
		self.init_prompt = init_prompt_arg

	def full_mayor_prompt(self) -> str :
		return (self.mayor_prompt + self.common_instructions
			+ self.commoner_summon_instructions)

	def full_scientist_prompt(self) -> str :
		return (self.scientist_prompt + self.common_instructions
			+ self.commoner_summon_instructions)

	def full_advocate_prompt(self) -> str :
		return (self.advocate_prompt + self.common_instructions
			+ self.commoner_summon_instructions)

	def full_disaster_prompt(self) -> str :
		return self.disaster_prompt + self.common_instructions