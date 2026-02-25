from typing import cast

from telegram import Update
from telegram.ext import ContextTypes, filters

from puregym_bot.config import config
from puregym_bot.puregym.client import PureGymClient


async def on_startup(app):
    client = PureGymClient(config.PUREGYM_USERNAME, config.PUREGYM_PASSWORD)
    await client.login()
    app.bot_data["puregym_client"] = client


async def on_shutdown(app):
    client = app.bot_data.get("puregym_client")
    if client is not None:
        await client.aclose()


AUTH_FILTER = filters.User(config.TELEGRAM_ID_WHITELIST)


def require_client(handler):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        client = cast(PureGymClient, context.bot_data["puregym_client"])
        return await handler(update, context, client)

    return wrapper
