import logging

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

from puregym_bot.config import config
from puregym_bot.puregym_client import PureGymClient

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat is None:
        return

    await context.bot.send_message(
        chat_id=update.effective_chat.id, text="I'm a bot, please talk to your hand!"
    )


if __name__ == "__main__":
    client = PureGymClient(config.PUREGYM_USERNAME, config.PUREGYM_PASSWORD)

    # application = (
    #     ApplicationBuilder().token(config.TELEGRAM_TOKEN.get_secret_value()).build()
    # )
    # start_handler = CommandHandler("start", start)
    # application.add_handler(start_handler)

    # application.run_polling()
