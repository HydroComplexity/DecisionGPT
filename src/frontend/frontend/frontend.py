import os
import reflex as rx

from frontend import style
from frontend.states.chat_state import ChatState
from frontend.states.prompt_state import PromptState
from frontend.components.prompt_modifier import render_prompt_box
from frontend.components.chat_interface import chat_interface


print(os.getenv("REFLEX_HOT_RELOAD_EXCLUDE_PATHS"), flush=True)

def index() -> rx.Component:
	
	return rx.box(
		chat_interface(),
		rx.cond(PromptState.init_prompt_show, render_prompt_box("init")),
		rx.cond(PromptState.mayor_prompt_show, render_prompt_box("mayor")),
		rx.cond(PromptState.scientist_prompt_show, render_prompt_box("scientist")),
		rx.cond(PromptState.advocate_prompt_show, render_prompt_box("advocate")),
		on_mount=ChatState.initial_connect,
		class_name="!bg-slate-50 w-screen h-screen",
	)


app = rx.App(stylesheets=["style.css"])
app.add_page(index)