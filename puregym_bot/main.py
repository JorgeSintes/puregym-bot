import logging

from puregym_bot.bot.app import build_app

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)


if __name__ == "__main__":
    application = build_app()
    application.run_polling()
