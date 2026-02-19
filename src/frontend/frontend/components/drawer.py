import reflex as rx
from frontend.components.prompt_modifier import render_prompt_box
from frontend.states.prompt_state import PromptState


class SpeedDial(rx.ComponentState) :
	is_open: bool = False

	@rx.event
	def test_print(self) :
		print("pouet", flush=True)

	@rx.event
	def toggle(self, value: bool) :
		self.is_open = value

	@classmethod
	def get_component(cls, **props) :

		def menu_item(icon: str, text: str, role: str) -> rx.Component :
			return rx.hstack(
				rx.icon(icon, padding="2px"),
				rx.text(text, weight="medium"),
				align="center",
				opacity="0.75",
				cursor="pointer",
				_hover={
					"opacity" : "1",
				},
				width="100%",
				align_items="center",
				on_click=PromptState.toggle_prompt(role),
			)

		def menu() -> rx.Component : 
			return rx.box(
				rx.card(
					rx.vstack(
						menu_item("file-type-2", "Change Init Prompt", "init"),
						rx.divider(margin="0"),
						menu_item("file-user", "Change Mayor Prompt", "mayor"),
						rx.divider(margin="0"),
						menu_item("file-user", "Change Scientist Prompt", "scientist"),
						rx.divider(margin="0"),
						menu_item("file-user", "Change Community Advocate Prompt", "advocate"),
						direction="column-reverse",
						align_items="end",
						justify_content="end",
					),
					box_shadow="0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rbg(0 0 0 / 0.1)",
				),
				position="absolute",
				bottom="100%",
				width="384px",
				right="0%",
				padding_right="50px",
				padding_bottom="25px",
			)

		return rx.container(
			rx.icon_button(
				rx.icon(
					"plus",
					style={
						"transform" : rx.cond(
							cls.is_open,
							"rotate(45deg)",
							"rotate(0)",
						),
						"transition" : "transform 150ms cubic-bezier(0.4, 0, 0.2, 1)"
					},
					class_name="dial",
				),
				variant="solid",
				# color_scheme="teal",
				size="3",
				cursor= "pointer",
				radius="full",
				position= "relative",
				class_name="bg-teal-500 hover:bg-teal-600"
			),
			rx.cond(
				cls.is_open,
				menu(),
			),
			position="relative",
			on_mouse_enter=cls.toggle(True),
			on_mouse_leave=cls.toggle(False),
			on_click=cls.toggle(~ cls.is_open),
			**props,
			class_name="!p-0 align-center justify-center"
		)


speed_dial_reveal = SpeedDial.create


def render_reveal() :
	return rx.container(
		speed_dial_reveal(),
		class_name="h-full w-[10%] align-center justify-center !p-0"
	)
