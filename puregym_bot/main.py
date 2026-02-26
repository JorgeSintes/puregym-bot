import logging

from puregym_bot.bot.app import build_app
from puregym_bot.config import config
from puregym_bot.storage.db import init_db

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, config.logging_level.upper(), logging.INFO),
)


if __name__ == "__main__":
    init_db(config.users)
    application = build_app()
    application.run_polling()
