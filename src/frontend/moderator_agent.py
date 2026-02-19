import re
import ast
import json
import time
import logging
import pprint
import threading
import asyncio
import traceback
import datetime

import numpy.linalg as la
import multiprocessing as mp
from msg_queue import GPTQueue
from prompt_state_genai import PromptStateGenAI

from multiprocessing.managers import ListProxy
from pika.exceptions import AMQPChannelError, AMQPConnectionError

from dotenv import load_dotenv

from typing import AsyncGenerator, Optional, Any, Dict
from typing_extensions import override

from google.genai import types

from openai import AzureOpenAI

from google.adk.events import Event, EventActions
from google.adk.runners import Runner
from google.adk.models import LlmResponse, LlmRequest
from google.adk.models.lite_llm import LiteLlm
from google.adk.sessions import InMemorySessionService
from google.adk.agents import Agent, BaseAgent, LlmAgent
from google.adk.agents.loop_agent import LoopAgent
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.invocation_context import InvocationContext

from google.adk.tools import FunctionTool
from google.adk.tools.tool_context import ToolContext
from google.adk.tools.base_tool import BaseTool


######################### CONSTANTS ############################################

GREEN = '\033[92m'
WARNING = '\033[93m'
INFO = '\033[94m'
ENDC = '\033[0m'
FAIL = '\033[91m'

APP_NAME 		= "adk-summit"
USER_ID 		= "user1"
SESSION_ID	= "session001"

MODEL_ID = "azure/o_series/gpt-4.1-mini"
VALIDATOR_MODEL_ID = "azure/gpt-5-mini"
SUMMARIZER_MODEL_ID = "azure/gpt-5"
EMBEDDING_MODEL_ID = "text-embedding-3-large"

SUMMONING_COOLDOWN = 3
STARTING_TIME = "2025-07-04T06:00:00"

##################################### CONFIG ###################################

load_dotenv(dotenv_path=".env")

azure_client = AzureOpenAI(api_version="2025-03-01-preview")

prompts = PromptStateGenAI()

queue = GPTQueue("amqp://guest:guest@queue/")
queue.connect()


def run_publish_loop(shared_list_arg) :
	queue.publish_loop(shared_list_arg)


################################ Embedding Functions ###########################

def word_embedding(word_arg) :
	response = azure_client.embeddings.create(
		input=[word_arg],
		model=EMBEDDING_MODEL_ID
	)

	if len(response.data) > 1 :
		print("there is problem, response should be of size 1")

	else :
		return response.data[0].embedding

def rbf_kernel(x, sigma):
	"""Compute the RBF (Gaussian) kernel matrix for a 1D array."""
	x = x[:, None]
	sq_dists = (x - x.T)**2

	if sigma is None:
		# Compute pairwise distances (nonzero only)
		dists = np.sqrt(sq_dists[np.triu_indices_from(sq_dists, k=1)])
		median_dist = np.median(dists)
		sigma = median_dist if median_dist > 0 else 1.0  # fallback for constant data

	return np.exp(-sq_dists / (2 * sigma**2))

def hsic(X, Y, sigma):
	"""Compute empirical HSIC using RBF kernels."""
	n = len(X)
	K = rbf_kernel(np.array(X), sigma)
	L = rbf_kernel(np.array(Y), sigma)
	H = np.eye(n) - np.ones((n, n)) / n
	HSIC_value = np.trace(K @ H @ L @ H) / (n - 1)**2
	return HSIC_value

def normalized_hsic(X, Y, sigma):
	"""Normalized HSIC (bounded in [0,1])."""
	hsic_xy = hsic(X, Y, sigma)
	hsic_xx = hsic(X, X, sigma)
	hsic_yy = hsic(Y, Y, sigma)
	return hsic_xy / np.sqrt(hsic_xx * hsic_yy)

def compare_hsic(dataset) :
	result = []
	for data in dataset :
		emb = [word_embedding(w) for w in data]

		for i in range(len(data)-1) :
			val = normalized_hsic(emb[i],emb[i+1], sigma=1)
			cossimilarity = np.dot(emb[i], emb[i+1])/(la.norm(emb[i])*la.norm(emb[i+1]))
			result.append({"input_1" : "input prompt", "input_2" : data[i+1], "hsic" : val,
				"cosine": cossimilarity})

	sorted_result = sorted(result, key=lambda t: t["hsic"], reverse=True)
	return sorted_result

def hsic_embedding(
	args: str,
	tool_context: ToolContext
	) -> Optional[Dict] :
	""" Evaluates the information yield of substaks compared to an original task.
	"""

	print(f"[hsic_embedding_tool] Entered tool execution callback.", flush=True)


	main_task = tool_context.state.get("main_task")

	print(f"[hsic_embedding_tool] This is main task retrieved from context: {main_task}", flush=True)
	print(f"[hsic_embedding_tool] This is args passed: {args}")
	print(f"[hsic_embedding_tool] args type: {type(args)}", flush=True)


	subtasks = ast.literal_eval(args.replace("subtasks = ", "").replace("subtasks=", ""))

	dataset = [[main_task, subtask] for subtask in subtasks]
	output_dataset = compare_hsic(dataset)

	print(output_dataset)
	return output_dataset

task_breaker_agent = LlmAgent(
	name="task_breaker_agent",
	model=LiteLlm(model=MODEL_ID),
	# model=LiteLlm(model=VALIDATOR_MODEL_ID),
	description="""You are an agent that breaks down a problem into sub-tasks.""",
	instruction='''Output a python array of the form [element, element, ...],
	that breaks down the input task into subtasks. Example: task: Bake a cake.
	Output: ["breaks eggs", "add flour", "preheat oven", etc...]. Make sure that the output can be parsed with ast.literal_eval and will not throw an exception.''',
)

def tasks_in_context(
	callback_context: CallbackContext) -> Optional[types.Content] :
	"""
	"""

	print(dir(callback_context), flush=True)
	return None

hsic_agent = LlmAgent(
	name="hsic_agent",
	model=LiteLlm(model=VALIDATOR_MODEL_ID),
	description="""You are an agent that evaluates subtasks.""",
	instruction='''Use the subtasks python array as an input for HSIC tool. Use the result in order to determine the top 5 most important tasks. Report in JSON following this template: {"top_tasks" : [task1, task2, task3]}''',
	tools=[hsic_embedding],
	output_key="task_ranking",
	# after_agent_callback=tasks_in_context,
)


class TaskAgent(BaseAgent) :
	"""Custom agent that aims to orchestrate discourse between several actors.

	This agents orchestrates a disaster crisis management session, and evaluates
	whether sufficient measures are taken to address the current challenge.
	The session runs until a satisfactory set of actions is generated.
	"""

	task_breaker_agent	: 		LlmAgent
	hsic_agent					: 		LlmAgent
	hsic_test						:			SequentialAgent
	shared_list					:			ListProxy

	def __init__(self, name: str, task_breaker_agent: Agent, hsic_agent: Agent,
		shared_list: ListProxy) :
		"""
		"""

		hsic_test = SequentialAgent(
			name="hsic_test",
			sub_agents=[task_breaker_agent, hsic_agent]
		)

		sub_agent_list = [hsic_test]

		super().__init__(
			name=name,
			task_breaker_agent=task_breaker_agent,
			hsic_agent=hsic_agent,
			hsic_test=hsic_test,
			sub_agents=sub_agent_list,
			shared_list=shared_list,
		)

	@override
	async def _run_async_impl(
		self, ctx: InvocationContext) -> AsyncGenerator[Event, None] :
		"""
		Implements the custom orchestration logic for the workflow.
		"""
		async for event in self.hsic_test.run_async(ctx) :
			print(f"[{self.name}] generated event.", flush=True)
			try :
				yield event

			except ValueError :
				print(WARNING + "Caught a ValueError at top level, proceeding..." + ENDC, flush=True)

			body = event.model_dump_json(indent=2, exclude_none=True) 
			self.shared_list.append(body)

################################# Custom Agents ################################

class EscalatorAgent(BaseAgent) :
	"""
	"""
	async def _run_async_impl(
		self, ctx: InvocationContext) -> AsyncGenerator[Event, None] :
		"""
		"""
		decision = ctx.session.state.get("decision")
		stop_and_summon = ctx.session.state.get("stop_and_summon")
		itleft = ctx.session.state.get("interactions_left")
		# print(type(decision), type(stop_and_summon))

		print(
			INFO +
			f"[{self.name}] Escalator agent is called, dec:{decision}, sum:{stop_and_summon}, itcnt:{itleft}" +
			ENDC, flush=True)

		if stop_and_summon or decision or (itleft <= 0):
			print(INFO + f"[{self.name}] Stopping...", flush=True)

		print(flush=True)

		yield Event(
						author=self.name,
						content=types.Content(
							parts=[types.Part(text="")],
							role="model"
						),
						actions=EventActions(escalate=decision or stop_and_summon
							or (itleft <= 0)),
					)

class DiscussionAgent(BaseAgent) :
	"""Custom agent that aims to orchestrate discourse between several actors.

	This agents orchestrates a disaster crisis management session, and evaluates
	whether sufficient measures are taken to address the current challenge.
	The session runs until a satisfactory set of actions is generated.
	"""

	mayor_agent: 			LlmAgent
	scientist_agent: 	LlmAgent
	community_agent: 	LlmAgent
	moderator_agent:	LlmAgent
	disaster_agent:		LlmAgent
	summoner_agent:		LlmAgent
	workflow_agent:		SequentialAgent
	workloop_agent:		LoopAgent
	summarizer_agent:	LlmAgent
	shared_list:			ListProxy
	iterations:			int
	model_config= 		{"arbitrary_types_allowed" : True}

	def __init__(self, name: str, mayor_agent: Agent, scientist_agent: Agent,
		community_agent: Agent, disaster_agent: Agent, summoner_agent: Agent, 
		summarizer_agent: Agent, shared_list: ListProxy, iterations: int) :
		"""
		"""

		moderator_agent = LlmAgent(
			name="moderator_agent",
			model=LiteLlm(model=VALIDATOR_MODEL_ID),
			sub_agents=[mayor_agent, scientist_agent, community_agent],
			description="""Main coordinator.""",
			instruction=prompts.moderator_instructions,
			before_agent_callback=reset_blocks,
		)

		escalator_agent = EscalatorAgent(
			name="escalator_agent"
		)

		workloop_agent = LoopAgent(
			name="workloop_agent",
			sub_agents=[moderator_agent, summoner_agent, disaster_agent, escalator_agent],
			max_iterations=iterations,
		)

		workflow_agent = SequentialAgent(
			name="workflow_agent",
			sub_agents=[workloop_agent, summarizer_agent]
		)

		# sub_agent_list = [workloop_agent]
		sub_agent_list = [workflow_agent]

		super().__init__(
			name=name,
			mayor_agent=mayor_agent,
			scientist_agent=scientist_agent,
			community_agent=community_agent,
			disaster_agent=disaster_agent,
			summoner_agent=summoner_agent,
			moderator_agent=moderator_agent,
			workloop_agent=workloop_agent,
			workflow_agent=workflow_agent,
			summarizer_agent=summarizer_agent,
			sub_agents=sub_agent_list,
			shared_list=shared_list,
			iterations=iterations,
		)

	def log_transfer(
		self, callback_context: CallbackContext, llm_response: LlmResponse
		) -> Optional[LlmResponse] :
		"""
		"""
		try :
			transferred = llm_response.model_dump()["content"]["parts"][0]
			transferred = transferred["function_call"]["args"]["agent_name"]
			print(f"[{self.name}] Execution transfered to: {transferred}", flush=True)
			print()

		except TypeError :
			pass

		except IndexError :
			print(WARNING + "Discard empty message." + ENDC)
			print(llm_response.model_dump(), flush=True)


	@override
	async def _run_async_impl(
		self, ctx: InvocationContext) -> AsyncGenerator[Event, None] :
		"""
		Implements the custom orchestration logic for the workflow.
		"""
		# it = 0
		# 1. Await from messages generated from the loop workflow

		async for event in self.workflow_agent.run_async(ctx) :
			# print(f"[{self.name}] generated event.", flush=True)
			try :
				yield event

			except ValueError :
				print(WARNING + "Caught a ValueError at top level, proceeding..." + ENDC, flush=True)

			# print(f"IT: {it}, {ctx.session.state.get('stop_and_summon')}", flush=True)

			# it += 1
			body = event.model_dump_json(indent=2, exclude_none=True) 
			self.shared_list.append(body)

################ CALLBACKS #############


import pandas as pd
import numpy as np

def read_guadalupe(timestamp: str) -> np.float64 :
	data = pd.read_feather("/mnt/resources/guadalupe.fth")
	return data.iloc[(data["timedate"] - pd.to_datetime(timestamp))
		.abs().argmin()].stage_height

def get_river_height(
	timestamp: str,
	tool_context: ToolContext
	) -> str :
	"""Retrieves the river stage height for a given timestamp. The timestamp
	should be in the following format: yyyy-mm-dd HH:MM:SS

	Returns: a str of the stage height at that timestamp.
	"""
	print(FAIL + "TOOL CALLED" + ENDC, flush=True)
	stage_height = read_guadalupe(timestamp)
	return timestamp, str(stage_height)


def check_role(
	callback_context: CallbackContext,
	llm_request: LlmRequest) -> Optional[types.Content] :
	"""
	"""
	print(llm_request.model_dump_json(indent=2, exclude_none=True))


def decision_pattern(
	decision: bool,
	justification: str) -> Optional[Dict] :
	"""This tool returns an object containing the decision of the disaster agent
	as well as the justification leading to make this decision.
	"""
	return {"call_type" : "tool", "decision": decision, "justification": justification}


def reset_blocks(
	callback_context: CallbackContext) -> Optional[types.Content] :
	"""
	"""
	callback_context.state.update(
		{
			"block_tool_disaster": False,
			"block_tool_summon" : False,
			"interactions_left": callback_context.state.get("interactions_left") -1,
		}
	)
	

def write_decision_context(
	tool: BaseTool,
	args: Dict[bool, str],
	tool_context: ToolContext,
	tool_response: Dict) -> Optional[Dict] :
	"""
	Write the decision and justification of the disaster agent in the
	context, in order for the escalator agent to be able to make decisions.
	"""

	# prevent tool from executing indefinitely
	if tool_context.state.get("block_tool_disaster") :
		# tool_context.state.update({"block_tool_disaster" : False})
		tool_context.actions.transfer_to_agent = "escalator_agent"

	else :
		# print(GREEN + "After tool callback called" + ENDC, flush=True)
		tool_context.state.update(
			{
				"decision": args["decision"],
				"justification": args["justification"],
				"block_tool_disaster" : True
			}
		)
		args["call_type"] = "after_tool_callback"
		return args


def summon_agent(
	agent_profile: str,
	agent_description: str) -> Optional[Dict] :
	""" This tool allows to create an agent profile and description from
	requests identified in the conversation. If multile profiles are named,
	pick ONE, the most relevant.
	"""
	print(FAIL +
		f"[Agent summoner] The agent {agent_profile} has been called for summoning..."
		+ ENDC, flush=True)
	
	return {
		"agent_profile" : agent_profile, "agent_description": agent_description}


def after_summon(
	tool: BaseTool,
	args: Dict[str, Any],
	tool_context: ToolContext,
	tool_response: Dict) -> Optional[Dict] :
	"""
	"""

	if tool_context.state.get("block_tool_summon") :
		tool_context.actions.transfer_to_agent = "escalator_agent"
		# tool_context.actions.escalate = True

		print(FAIL + f"[Summon tool] Skipping tool and escalating...\n" + ENDC, flush=True)

	else :
		agent_profile = args["agent_profile"]
		agent_profile = agent_profile.replace('-', '_')
		agent_profile = re.sub(r'[^\w\s]', '', agent_profile)
		agent_profile = re.sub(r'\s+', '', agent_profile)

		tool_context.state.update({
			"stop_and_summon" : True,
			"agent_profile" : agent_profile.lower(),
			"agent_description" : args["agent_description"],
			"block_tool_summon" : True,
			"open_seats" : tool_context.state.get("open_seats") -1,
			"summoning_cooldown" : SUMMONING_COOLDOWN,
		})
		# print(FAIL + f"[Summon tool] Stop flag has been set to true." + ENDC, flush=True)

	return None

def suppress_output(
	callback_context: CallbackContext) -> Optional[types.Content] :
	"""
	"""
	return types.Content(
		parts=[types.Part(text="")], role="model")


def check_open_seats(
	callback_context: CallbackContext) -> Optional[types.Content] :
	"""Check if the summoner agent can summon other agents based on the 
	number of seats left around the table.
	"""

	if ((callback_context.state.get("open_seats") > 0) and
		(callback_context.state.get("summoning_cooldown") == 0 )) :

		return None

	else :
		# not the last iteration of the subtask

		if callback_context.state.get("open_seats") > 0 :
			callback_context.state.update(
				{
					"summoning_cooldown" : callback_context.state
						.get("summoning_cooldown")-1
				}
			)
			return types.Content(
				parts=[types.Part(text="[SKIP] Summoning cooling down...")],
				role="model"
			)

		else :
			return types.Content(
				parts=[types.Part(text="[SKIP] No more summoning seats around the table...")],
				role="model"
			)


def check_if_summarize(
	callback_context: CallbackContext) -> Optional[types.Content] :
	"""Check if the agent should run, based on the multiple stopping conditions
	"""

	if (
		# callback_context.state.get("decision") or
		((callback_context.state.get("subtasks_left") == 0) and (callback_context.state.get("interactions_left") == 0))
		):
		# no changes to the inputs
		# run summarizer agent.
		return None

	else :
		# stop is a result of summoning
		return types.Content(
			parts=[types.Part(text="[SKIP] Skipped agent execution.")],
			role="model"
		)


def check_if_evaluate(
	callback_context: CallbackContext) -> Optional[types.Content] :
	"""Check if the agent should run, based on the multiple stopping conditions
	"""
	if callback_context.state.get("interactions_left") == 0 :
		return None

	else :

		if callback_context.state.get("block_tool_disaster") :
			# not the last iteration of the subtask
			return types.Content(
				parts=[types.Part(text="[SKIP] ")],
				role="model"
			)

		else :
			return types.Content(
				parts=[types.Part(text="[SKIP] Evaluator runs at end of task...")],
				role="model"
			)

def clear_summoner_output(
	callback_context: CallbackContext,
	llm_response: LlmResponse
	) -> Optional[LlmResponse] : 
	"""
	"""
	return LlmResponse(
		content=types.Content(
			role="model",
			parts=[types.Part(text="")]
		)
	)

############### AGENTS #########################

disaster_agent = LlmAgent(
	name="disaster_agent",
	model=LiteLlm(model=VALIDATOR_MODEL_ID),
	sub_agents=[],
	description="""You are a disaster evaluation expert. Your goal is to evaluate
	whether an assessment of a disaster situation is satisfying to pursue an action plan.""",
	instruction=prompts.full_disaster_prompt(),
	input_schema=None,
	disallow_transfer_to_peers=True,
	disallow_transfer_to_parent=True,
	tools=[decision_pattern],
	after_tool_callback=write_decision_context,
	before_agent_callback=check_if_evaluate,
)

summoner_agent = LlmAgent(
	name="summoner_agent",
	model=LiteLlm(model=VALIDATOR_MODEL_ID),
	sub_agents=[],
	description="""Your only role is to identify new agent profiles needed by the assembly,
	and use the summon_tool to invoke them.
	""",
	instruction=prompts.summoner_agent_instructions,
	disallow_transfer_to_peers=True,
	disallow_transfer_to_parent=True,
	tools=[summon_agent],
	before_agent_callback=check_open_seats,
	after_tool_callback=after_summon,
	after_agent_callback=suppress_output,
)

summarizer_agent = LlmAgent(
	name="summarizer_agent",
	model=LiteLlm(model=SUMMARIZER_MODEL_ID),
	sub_agents=[],
	description="""You are a neat, thorough and tidy summarizer.""",
	instruction=prompts.summarizer_prompt,
	input_schema=None,
	disallow_transfer_to_peers=True,
	disallow_transfer_to_parent=True,
	before_agent_callback=check_if_summarize,
)


async def call_agent(
	runner_arg: Runner,
	shared_list_arg = None,
	user_input_topic: str | None = None) :
	"""
	If called with user_input_topic, start execution.
	If called without, resume execution.
	"""
	current_session = await session_service.get_session(app_name=APP_NAME,
																								user_id=USER_ID,
																								session_id=SESSION_ID)

	if not current_session :
		# logger.error("Session not found...")
		return

	if user_input_topic :
		content = types.Content(role="user", parts=[types.Part(
			text=user_input_topic)])

		msg_template = {"content":{"parts":[
			{"text":user_input_topic}
			],"role":"user"},"author":"user"}

		shared_list_arg.append(json.dumps(msg_template))

		events = runner_arg.run(
			user_id=USER_ID, session_id=SESSION_ID, new_message=content)
		
		print(GREEN + f"[MAIN] Starting framework..." + ENDC, flush=True)
		print()

	else :
		resume_content = types.Content(role="user", parts=[types.Part(
			text="Resuming conversation.")]
		)
		events = runner_arg.run(
			user_id=USER_ID, session_id=SESSION_ID, new_message=resume_content)

		print(GREEN + f"[MAIN] Resuming framework after summon..." + ENDC, flush=True)
		print()

	final_response = "No final response captured."

	# might have to move this line up
	# but have to merge the two generators
	# from the two runner.run
	for event in events :
		if event.is_final_response() and event.content and event.content.parts :
			final_response = event.content.parts[0].text

	final_session = await session_service.get_session(app_name=APP_NAME,
																							user_id=USER_ID,
																							session_id=SESSION_ID)


async def save_conversation_history_json(session_manager, shared_list_arg) :
	"""
	"""
	out_file = open(f"/logs/new_midwest/{datetime.datetime.now()}.log", mode="w")

	sess = await session_manager.get_session(
		app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)

	messages = []

	for ev in sess.events :
		messages.append(ev.model_dump_json())

	out_file.write(json.dumps(messages))
	out_file.close()


def create_new_agent(name_arg: str, profile_arg: str) -> LlmAgent:
	"""
	"""
	agent_desc = f"""You are a {' '.join(name_arg.split('_'))} agent. 
	You have been added to this discussion group to discuss an imminent crisis.
	"""

	new_agent = LlmAgent(
		name=name_arg, 
		model=LiteLlm(model=MODEL_ID),
		sub_agents=[],
		description=agent_desc,
		instruction = profile_arg + prompts.common_instructions,
		input_schema=None,
		disallow_transfer_to_peers=True,
		disallow_transfer_to_parent=True,
	)

	return new_agent


def shutdown(shared_list_arg) :
	"""
	"""
	shared_list_arg.append(json.dumps({"command" : "shutdown"}))


############################## MAIN ############################################

session_service = InMemorySessionService()
initial_state = {
	"decision" : False,
	"justification" : "",
	"stop_and_summon" : False,
	"subtasks_left" : 0,
	"interactions_left" : 0,
	"interactions" : 15,
	"agent_profile" : "",
	"agent_description" : "",
	"block_tool_disaster": False,
	"block_tool_summon": True,
	"open_seats" : 3,
	"main_task" : prompts.init_prompt,
	"task_ranking" : "",
	"summoning_cooldown" : 0,
}

session = asyncio.run(session_service.create_session(
	app_name=APP_NAME,
	user_id=USER_ID,
	session_id=SESSION_ID,
	state=initial_state
))


if __name__ == "__main__" :	
	manager = mp.Manager()
	shared_list = manager.list()

	publish_loop_process = mp.Process(
		target=run_publish_loop, args=(shared_list,))
	publish_loop_process.start()

	received_prompt = queue.wait_for_frontend_signal()
	prompts.replace_modifiable_prompts(**received_prompt)

	# print(prompts.full_mayor_prompt(), flush=True)

	mayor_agent = LlmAgent(
		name="mayor_agent",
		model=LiteLlm(model=MODEL_ID),
		sub_agents=[],
		description="""You are the mayor of a midwestern town. You address challenges pertaining
		to the wellbeing of the population, infrastructure and political choices.""",
		instruction=prompts.full_mayor_prompt(),
		input_schema=None,
		disallow_transfer_to_peers=True,
		disallow_transfer_to_parent=True,
	)

	scientist_agent = LlmAgent(
		name="scientist_agent",
		model=LiteLlm(model=MODEL_ID),
		sub_agents=[],
		description="""You are a civil and environmental engineering doctor. You address
		questions and challenges that are related to infrastructure engineering, hydrology,
		reservoir operation, etc. You can use a tool to measure the river's height.""",
		instruction=prompts.full_scientist_prompt(),
		input_schema=None,
		disallow_transfer_to_peers=True,
		disallow_transfer_to_parent=True,
		tools=[get_river_height],
	)

	community_agent = LlmAgent(
		name="community_agent",
		model=LiteLlm(model=MODEL_ID),
		sub_agents=[],
		description="""You are a community advocate that protects vulnerable communities
		and fights against social and economic inequalities.""",
		instruction=prompts.full_advocate_prompt(),
		input_schema=None,
		disallow_transfer_to_peers=True,
		disallow_transfer_to_parent=True,
	)

	discussion_agent = DiscussionAgent(
		name="discussion_agent",
		mayor_agent=mayor_agent,
		scientist_agent=scientist_agent,
		community_agent=community_agent,
		disaster_agent=disaster_agent,
		summoner_agent=summoner_agent,
		shared_list=shared_list,
		summarizer_agent=summarizer_agent,
		iterations=100
	)

	task_agent = TaskAgent(
		name="task_agent",
		task_breaker_agent=task_breaker_agent,
		hsic_agent=hsic_agent,
		shared_list=shared_list,
	)

	runner_task = Runner(
		agent = task_agent,
		app_name=APP_NAME,
		session_service=session_service,
	)

	# initial run
	asyncio.run(call_agent(runner_task, shared_list, prompts.init_prompt))
	# when we exit, the execution has been interrupted either because the framework
	# is over either because we need to summon an agent.
	print(GREEN + f"[MAIN] Initial execution stopped..." + ENDC, flush=True)

	post_sess = asyncio.run(session_service.get_session(
		app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID))

	subtasks = json.loads(post_sess.state.get("task_ranking"))
	print(WARNING + f"[MAIN] Subtasks: {subtasks}" + ENDC, flush=True)

	# print(dir(post_sess.state), flush=True)

	post_sess.state.update({"subtasks_left" : len(subtasks["top_tasks"])})
	session_service.sessions[APP_NAME][USER_ID][SESSION_ID].state["subtasks_left"] = len(subtasks["top_tasks"])
	print(INFO + f"[MAIN] Subtasks left: {post_sess.state.get('subtasks_left')}" + ENDC, flush=True)

	runner = Runner(
		agent=discussion_agent,
		app_name=APP_NAME,
		session_service=session_service
	)

	for st in range(len(subtasks["top_tasks"])) :
		post_sess = asyncio.run(session_service.get_session(
			app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID))

		print(WARNING + f"[MAIN] Starting new sub-task..." + ENDC, flush=True)

		post_sess.state.update({"subtasks_left" : post_sess.state.get("subtasks_left") - 1})
		session_service.sessions[APP_NAME][USER_ID][SESSION_ID].state["subtasks_left"] = post_sess.state.get("subtasks_left")

		print(INFO + f"[MAIN] Tring to rewrite state..." + ENDC, flush=True)
		print(INFO + f"[MAIN] {post_sess.state.get('interactions_left')}", flush=True)

		post_sess.state.update({"interactions_left" : post_sess.state.get("interactions")})
		session_service.sessions[APP_NAME][USER_ID][SESSION_ID].state["interactions_left"] = post_sess.state.get("interactions")

		print(INFO + f"[MAIN] {post_sess.state.get('interactions_left')}", flush=True)

		while post_sess.state.get("interactions_left") > 0 :
			# don't enter the loop if the reason we got out of the framework is not
			# summoning, but decision, or there are no interaction budget left.

			if post_sess.state.get("interactions_left") == post_sess.state.get("interactions") :
				# case when there is a new task that starts

				new_task_template = f"Let's proceed with the treatment of this subtask: {subtasks['top_tasks'][st]}"
				new_task_template += f" 2 hours have passed."
				asyncio.run(call_agent(runner, shared_list, new_task_template))

			else :
				if (post_sess.state.get("agent_profile")
					and post_sess.state.get("agent_description")) :

					print(GREEN + f"[MAIN] Creating new agent..." + ENDC, flush=True)
					nagent = create_new_agent(
						post_sess.state.get("agent_profile"),
						post_sess.state.get("agent_description"))
					discussion_agent.moderator_agent.sub_agents.append(nagent)

					# reset stopping flag
					post_sess.state.update(
						{
							"stop_and_summon" : False,
							"agent_profile" : "",
							"agent_description" : ""
						}
					)
					session_service.sessions[APP_NAME][USER_ID][SESSION_ID].state["stop_and_summon"] = False
					session_service.sessions[APP_NAME][USER_ID][SESSION_ID].state["agent_profile"] = ""
					session_service.sessions[APP_NAME][USER_ID][SESSION_ID].state["agent_description"] = ""


					runner = None
					runner = Runner(
						agent=discussion_agent,
						app_name=APP_NAME,
						session_service=session_service
					)

					ag_list = [
						ag.name for ag in discussion_agent.moderator_agent.sub_agents]

					print(GREEN + f"[MAIN] New agent added, the current agent lineup is the following:" + ENDC)
					print(ag_list)
					print(flush=True)
				

				else :
					print(FAIL + f"[MAIN] We shouldn't be here...." + ENDC, flush=True)
					print(post_sess.state, flush=True)
					time.sleep(5)

				asyncio.run(call_agent(runner, shared_list))

			post_sess = asyncio.run(session_service.get_session(
				app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID))

			print(INFO + f"[STATE CHECK] {post_sess.state}" + ENDC, flush=True)

	print(f"[MAIN] Execution completed.", flush=True)

	asyncio.run(save_conversation_history_json(session_service, shared_list))

	shutdown(shared_list)
	publish_loop_process.join()





