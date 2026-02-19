import reflex as rx
from frontend.states.chat_state import Message


def received_message_bubble(message_text: str, sender_name: str) -> rx.Component :
	return rx.el.div(
		rx.el.p(sender_name, class_name="text-xs text-slate-700 mb-1"),
		rx.el.p(
			message_text, class_name="text-sm sm:text-base"
		),
		class_name="text-black bg-gray-200 px-3 py-2 rounded-xl w-fit self-start max-w-[90%]",
	)

def markdown_message_bubble(message_text: str, sender_name: str) -> rx.Component :
	return rx.el.div(
		rx.el.p(sender_name, class_name="text-xs text-slate-700 mb-1"),
		rx.el.p(
			message_text, class_name="text-sm sm:text-base"
		),
		class_name="text-black bg-blue-100 px-3 py-2 rounded-xl w-fit self-start max-w-[90%]",
	)


def user_message_bubble(message_text: str, sender_name: str) -> rx.Component :
	return rx.el.div(
		rx.el.p(sender_name, class_name="text-xs text-slate-700 mb-1"),
		rx.el.p(
			message_text, class_name="text-sm sm:text-base"
		),
		class_name="text-black bg-red-100 px-3 py-2 rounded-xl w-fit self-start max-w-[90%]",
	)

def system_message(message_text: str, sender_name: str) -> rx.Component :
	return rx.box(
		rx.text(message_text, color="gray", font_style="italic", font_size="1em"),
		border_left="4px solid #ccc",
		padding_left="1em",
		margin_y="0em",
	)

def padding_message() -> rx.Component :
	return rx.box(
		rx.text("", font_size="1em"),
		border_left="4px solid",
		padding_left="1em",
		margin_y="0.2em",
		class_name="bg-slate-50"
	)

def message_bubble(message: Message) -> rx.Component :
	return rx.el.div(
		rx.cond(
			message["sender"] == "user",
			user_message_bubble(rx.html(message["text"]), message["sender"]),
			rx.cond(
				message["sender"] == "summarizer_agent", 
				received_message_bubble(rx.markdown(message["text"]), message["sender"]),
				rx.cond(
					message["message_type"] == "markdown",
					markdown_message_bubble(rx.markdown(message["text"]), message["sender"]),
					rx.cond(
						message["sender"] == "system", 
						system_message(message["text"], message["sender"]),
						rx.cond(
							message["sender"] == "padding",
							padding_message(),
							received_message_bubble(rx.html(message["text"]), message["sender"])
						)
					)
				)
			)
		),
		class_name="w-full flex flex-col gap-1 py-1",
	)
