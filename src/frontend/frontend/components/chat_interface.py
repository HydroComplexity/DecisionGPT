import reflex as rx
from frontend.components.message_bubble import message_bubble
from frontend.components.input_area import input_area
from frontend.components.upload_area import upload_area, download_button
from frontend.states.chat_state import ChatState

from frontend.components.drawer import render_reveal

def chat_interface() -> rx.Component :
	return rx.vstack(

		rx.box(
			# box for the conversation area, drawn in relative 85%
			rx.auto_scroll(
				rx.foreach(ChatState.messages, message_bubble),
				class_name="relative h-full flex-grow overflow-y-hidden p-4 space-y-2 bg-slate-50"
			),
			class_name="relative h-[93%] w-5/6",
			id="conversation_area"
		),

		rx.box(
			# box for the bottom bar, drawn in relative 15%
			rx.hstack(
				upload_area(),
				input_area(),
				download_button(),
				render_reveal(),
				class_name="flex w-full items-center"
			),
			class_name="relative h-[7%] w-full flex bg-zinc-200 p-0",
			id="bottom_bar"
		),

		rx.box(
			# box for the backdrop-blur, drawn in absolute
			class_name="absolute inset-0 border-none h-[20%] pt-px pb-px blur-gradient"
			# class_name="absolute inset-0 border-none h-[20%] pt-px pb-px backdrop-blur-sm bg-gradient-to-t from-slate/50 to-slate/10"
		),

		rx.box(
			# heading box, drawn in absolute
			rx.heading(
				"DecisionGPT.",
				size="8",
				color="#353535",
				align="right",
			),
			class_name="absolute h-64 w-screen inset-0 p-4"
		),

		class_name="flex h-screen w-screen relative inset-0 gap-0",
		id="main_stack"
	)