import reflex as rx

tailwind_config = {
	"plugins": ["@tailwindcss/typography"],
	"theme": {"extend": {"colors": {"primary": "#3b82f6"}}},
}


config = rx.Config(
	app_name = "frontend",
	ignore_patterns = ["tmp.log"],
	plugins=[rx.plugins.TailwindV3Plugin(tailwind_config)],
	# tailwind=True,
)
