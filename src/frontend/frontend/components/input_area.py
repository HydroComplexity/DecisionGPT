import reflex as rx
from frontend.states.chat_state import ChatState


def input_area() -> rx.Component:
	return rx.container(
		rx.el.form(
			rx.flex(
				rx.el.button(
					"Run Framework",
					type="submit",
					class_name="p-2 w-48 bg-teal-500 text-white rounded-tr-lg rounded-bl-lg hover:bg-teal-600 focus:outline-none focus:ring-2 focus:ring-blue-500",
				),
				direction="column",
				class_name="items-center",
			),
			on_submit=ChatState.set_ready,
			reset_on_submit=False,
			class_name="w-full",
		),
		class_name=" h-full border-none w-[20%] !p-0 align-center justify-center",
	)