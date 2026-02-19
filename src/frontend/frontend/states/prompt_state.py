import os
import json
import reflex as rx
import pandas as pd

GREEN = '\033[92m'
WARNING = '\033[93m'
INFO = '\033[94m'
ENDC = '\033[0m'
FAIL = '\033[91m'


def load_prompt(role_arg) :
	return open(f"prompts/{role_arg}.txt", "r").read()

class InitPromptText(rx.State) :

	text: str = load_prompt("init_prompt_v2")
	def reinit(self) :
		self.text = load_prompt("init_prompt_v2")

class MayorPromptText(rx.State) :
	text: str = load_prompt("mayor")

	def reinit(self) :
		self.text = load_prompt("mayor")

class ScientistPromptText(rx.State) :
	text: str = load_prompt("scientist")

	def reinit(self) :
		self.text = load_prompt("scientist")

class AdvocatePromptText(rx.State) :
	text: str = load_prompt("advocate")

	def reinit(self) :
		self.text = load_prompt("advocate")


class PromptState(rx.State) :
	# init_prompt: PromptText
	init_prompt_show: bool = False
	mayor_prompt_show: bool = False
	scientist_prompt_show: bool = False
	advocate_prompt_show: bool = False


	def toggle_prompt(self, role_arg) :

		if role_arg == "init" :
			self.init_prompt_show = not self.init_prompt_show
			print(f"Switching init prompt, now is {self.init_prompt_show}", flush=True)

		elif role_arg == "mayor" :
			self.mayor_prompt_show = not self.mayor_prompt_show
			print(f"Switching init prompt, now is {self.mayor_prompt_show}", flush=True)

		elif role_arg == "scientist" :
			self.scientist_prompt_show = not self.scientist_prompt_show
			print(f"Switching init prompt, now is {self.scientist_prompt_show}", flush=True)

		elif role_arg == "advocate" :
			self.advocate_prompt_show = not self.advocate_prompt_show
			print(f"Switching init prompt, now is {self.advocate_prompt_show}", flush=True)
