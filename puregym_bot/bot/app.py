from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler

from puregym_bot.bot import handlers
from puregym_bot.bot.dependencies import AUTH_FILTER, on_shutdown, on_startup
from puregym_bot.config import config


def build_app():
    application = (
        ApplicationBuilder()
        .token(config.telegram_token.get_secret_value())
        .post_init(on_startup)
        .post_shutdown(on_shutdown)
        .build()
    )
    start_handler = CommandHandler("start", handlers.start, filters=AUTH_FILTER)
    application.add_handler(start_handler)

    booked_classes_handler = CommandHandler("booked_classes", handlers.booked_classes, filters=AUTH_FILTER)
    application.add_handler(booked_classes_handler)
    all_classes_handler = CommandHandler("class_ids", handlers.all_class_ids, filters=AUTH_FILTER)
    application.add_handler(all_classes_handler)
    all_centers_handler = CommandHandler("center_ids", handlers.all_center_ids, filters=AUTH_FILTER)
    application.add_handler(all_centers_handler)

    test_inline_handler = CommandHandler("test_inline", handlers.test_inline, filters=AUTH_FILTER)
    application.add_handler(test_inline_handler)
    application.add_handler(CallbackQueryHandler(handlers.button))

    return application
