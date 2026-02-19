import reflex as rx
from frontend.states.prompt_state import PromptState, InitPromptText
from frontend.states.prompt_state import MayorPromptText, ScientistPromptText
from frontend.states.prompt_state import AdvocatePromptText

prompt_box_roles = {
	"init" : InitPromptText,
	"mayor" : MayorPromptText,
	"scientist" : ScientistPromptText,
	"advocate" : AdvocatePromptText,
}

class PromptBox(rx.ComponentState) :
	"""
	"""
	role: str


	@classmethod
	def get_component(cls, role_arg: str, **props) :

		return rx.box(
			rx.box(
				rx.vstack(
					rx.box(
						rx.heading(f"{role_arg.capitalize()} prompt", color="#353535", size="7"),
						class_name="relative h-[15%] w-full flex items-center justify-center"
					),
					rx.box(
						rx.text_area(
							value=prompt_box_roles[role_arg].text,
							on_change=prompt_box_roles[role_arg].set_text,
							variant="surface",
							style={
								"width" : "80%",
								"height" : "90%",
								"background-color" : "#FAFAFA",
								# "font-size" : "large",
								"fontWeight" : 700
							},
							class_name="[&>textarea]:!text-lg [&>textarea]:!font-medium",
						),
						class_name="relative h-[75%] w-full flex items-center justify-center"
					),
					rx.box(
						rx.button(
							"Reset Prompt",
							on_click=prompt_box_roles[role_arg].reinit(),
						),
						class_name="relative h-[15%] w-full flex items-center justify-center"
					),
					class_name="relative flex flex-col items-center justify-center h-full w-full"
				),
				rx.icon_button(
					rx.icon(
						"x",
					),
					# variant="solid",
					size="3",
					top="15px",
					right="15px",
					on_click=lambda : PromptState.toggle_prompt(role_arg),
					class_name="absolute bg-teal-500 hover:bg-teal-600"
				),
				# align_content="center",
				# justify_content="center",
				class_name="relative w-[85%] h-[85%] rounded-lg bg-stone-50 drop-shadow-sm",
				# class_name="relative w-[85%] h-[85%] rounded-lg bg-stone-200/30 drop-shadow-lg backdrop-blur-md",
				**props
			),
			class_name="inset-0 absolute h-screen w-screen flex items-center justify-center"
		) 

	# def close_box(self) :


prompt_box_spawn = PromptBox.create

def render_prompt_box(role_arg) :
	return rx.container(
		prompt_box_spawn(role_arg)
	)

