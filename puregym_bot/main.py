import logging

from puregym_bot.bot.app import build_app
from puregym_bot.config import get_config
from puregym_bot.storage.db import init_db


def main() -> None:
    config = get_config()
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=getattr(logging, config.logging_level.upper(), logging.INFO),
    )
    init_db()
    application = build_app()
    application.run_polling()


if __name__ == "__main__":
    main()
