from telegram import BotCommand
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler

from puregym_bot.bot import handlers
from puregym_bot.bot.dependencies import AUTH_FILTER, build_handler, on_shutdown, on_startup
from puregym_bot.bot.jobs import run_booking_cycle
from puregym_bot.bot.registry import COMMANDS
from puregym_bot.config import config


def build_app():
    async def post_init(app):
        await on_startup(app)
        await app.bot.set_my_commands([BotCommand(command.name, command.description) for command in COMMANDS])
        app.job_queue.run_repeating(run_booking_cycle, interval=60, first=0, name="booking_cycle")

    application = (
        ApplicationBuilder()
        .token(config.telegram_token.get_secret_value())
        .post_init(post_init)
        .post_shutdown(on_shutdown)
        .build()
    )

    for command in COMMANDS:
        application.add_handler(
            CommandHandler(
                command.name,
                build_handler(command.handler, allow_inactive=command.allow_inactive),
                filters=AUTH_FILTER,
            )
        )

    application.add_handler(CallbackQueryHandler(handlers.button))

    return application
