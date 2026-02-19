import reflex as rx
from frontend.states.chat_state import ChatState

def upload_area() -> rx.Component :
	return rx.container(
		rx.upload(
			rx.text("Drop conversation log to view"),
			id="file_upload",
			border="2px dashed #878787",
			padding=".5em",
			on_drop=ChatState.handle_upload(
				rx.upload_files(upload_id="file_upload")
			),

		),
		class_name="h-full w-[60%] !pt-2 !pb-2 align-center justify-center !pl-0 !pr-0"
		# class_name="h-full w-[90%] !pt-2 !pb-2 align-center justify-center"
		# class_name="h-full w-full !pt-2 !pb-2 flex-col"
	)

def download_button() -> rx.Component :
	return rx.container(
		rx.icon_button(
			rx.icon(
				"arrow-down-to-line"
			),
			size="3",
			# top="15px",
			# right="15px",
			on_click=ChatState.handle_download,
			class_name="relative rounded-tr-lg rounded-bl-lg bg-teal-500 hover:bg-teal-600"
		),
		position="relative",
		class_name="h-full w-[10%] !p-0 align-center justify-center"
	)
