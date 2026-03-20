from telegram import BotCommand
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, filters

from puregym_bot.bot import handlers
from puregym_bot.bot.booking_cycle import run_booking_cycle
from puregym_bot.bot.dependencies import build_handler, on_shutdown, on_startup
from puregym_bot.bot.registry import COMMANDS
from puregym_bot.config import get_config


def build_app():
    config = get_config()
    auth_filter = filters.User([config.telegram_id])

    async def post_init(app):
        await on_startup(app)
        await app.bot.set_my_commands([BotCommand(command.name, command.description) for command in COMMANDS])
        app.job_queue.run_repeating(
            run_booking_cycle, interval=config.booking_interval_seconds, first=0, name="booking_cycle"
        )

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
                filters=auth_filter,
            )
        )

    application.add_handler(CallbackQueryHandler(handlers.button))

    return application
