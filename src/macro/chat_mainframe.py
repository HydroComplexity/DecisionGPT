# import pika
import aiormq
from aiormq.exceptions import AMQPConnectionError
import json
import time
import datetime
import asyncio
from uuid import uuid4
from nicegui import ui, run, app

# RMQ_IP="170.0.0.2"
RMQ_IP="rmqueue"
RMQ_PORT="5672"

own_id = str(uuid4())
global_messages = []
colors = ["brown-6", "blue-grey-6", "indigo", "orange-6", "light-green-6",
	"teal-9", "blue-7", "pink-6", "purple-6", "deep-purple-7", "red-11", "cyan-3",
	"amber-4", "amber-10", "lime-14"]
color_attr = {"system" : "grey-1", "moderator" : "red-12"}

async def read_queue() -> None :
	print("Hard wait for connection", flush=True)
	
	# unfortunately necessary as I didn't find any simple and straightforward way
	# to combine aiormq, nicegui's asyncio loop and execption handling for 
	# AMQPConnection, in the case of a docker compose where the rabbitmq is slower
	# to start for instance

	time.sleep(5)

	connection = await aiormq.connect(f"http://{RMQ_IP}:{RMQ_PORT}")
	channel = await connection.channel()

	declare_ok = await channel.queue_declare("chat_comm")

	print(f"Connection statuses : {connection}{channel}{declare_ok}",
		flush=True)
	
	while not app.is_stopped or (queue_state.method.message_count == 0):
		msg = await channel.basic_get("chat_comm")

		if msg.body.decode() != "":
			# print(f"MESSAGE : {msg.body.decode()}", flush=True)
			try :
				msgobj = json.loads(msg.body.decode())

			except json.JSONDecodeError :
				print(f"##########FAILED JSON CONTENT: {msg}", flush=True)

			else :
				if "progress" in msgobj :
					progress.refresh(msgobj["progress"])
				else :
					global_messages.append(msgobj)
					chat_messages.refresh()

		else :
			print("MESSAGE: EMPTY", flush=True)

		await asyncio.sleep(.1)

@ui.refreshable
def progress(value_arg=0) -> None :
	"""
	"""
	if value_arg == "stop": 
		ui.linear_progress(
			value=value_arg, show_value=False).props(
			'instant-feedback').set_visibility(False)

	else :
		if value_arg < .5 : 
			color = "#34c6eb"
		elif value_arg >= .5 and value_arg <= .8 : 
			color = "#ffcc66"
		else :
			color = "#4ce660"

		ui.linear_progress(
			value=value_arg, show_value=False, color=color).props(
			'instant-feedback')#.set_visible(value_arg < 1)


@ui.refreshable
def chat_messages(opt_msg_list=[]) -> None :
	for msg_obj in global_messages + opt_msg_list:
		try :
			sel_color = color_attr[msg_obj["user_id"]]

		except KeyError :
			color_attr[msg_obj["user_id"]] = colors[len(color_attr.keys())]
			sel_color = color_attr[msg_obj["user_id"]]

		sel_text = "black" if (msg_obj["user_id"] == "system") else "white"

		ui.chat_message(
			text=msg_obj["text"],
			stamp=msg_obj["stamp"],
			avatar=msg_obj["avatar"],
			sent=(own_id == msg_obj["user_id"])
		).props(f'bg-color={sel_color} text-color={sel_text}')
	ui.run_javascript('window.scrollTo(0, document.body.scrollHeight)')
	ui.linear_progress(
			value=0, show_value=False).props(
			'instant-feedback').set_visibility(False)

@ui.page('/')
async def main() :
	avatar = f"https://robohash.org/{own_id}?bgset=set3"

	ui.add_css(r'a:link, a:visited {color: inherit !important; text-decoration: none; font-weight: 500}')
	with ui.footer().classes('bg-white'), ui.column().classes('w-full max-w-3xl mx-auto my-6'):
		with ui.row().classes('w-full no-wrap items-center'):
			with ui.avatar().on('click', lambda: ui.navigate.to(main)):
				ui.image(avatar)
		ui.markdown('DecisionGPT') \
			.classes('text-xs self-end mr-8 m-[-1em] text-primary')

	await ui.context.client.connected()  # chat_messages(...) uses run_javascript which is only possible after connecting
	ui.label("Generating conversation...").classes("mx-auto my-36")
	chat_messages()
	progress()

if __name__ in ["__main__", "__mp_main__"] :
	ui.run()
	app.on_startup(read_queue)






