from telegram.ext import ApplicationBuilder, CommandHandler

from puregym_bot.bot import handlers
from puregym_bot.bot.dependencies import AUTH_FILTER, on_shutdown, on_startup
from puregym_bot.config import config


def build_app():
    application = (
        ApplicationBuilder()
        .token(config.TELEGRAM_TOKEN.get_secret_value())
        .post_init(on_startup)
        .post_shutdown(on_shutdown)
        .build()
    )
    start_handler = CommandHandler("start", handlers.start, filters=AUTH_FILTER)
    application.add_handler(start_handler)

    booked_classes_handler = CommandHandler(
        "booked_classes", handlers.booked_classes, filters=AUTH_FILTER
    )
    application.add_handler(booked_classes_handler)
    all_classes_handler = CommandHandler(
        "class_ids", handlers.all_class_ids, filters=AUTH_FILTER
    )
    application.add_handler(all_classes_handler)
    all_centers_handler = CommandHandler(
        "center_ids", handlers.all_center_ids, filters=AUTH_FILTER
    )
    application.add_handler(all_centers_handler)

    return application
