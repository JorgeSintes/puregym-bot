from typing import cast

from telegram import Update
from telegram.ext import ContextTypes, filters

from puregym_bot.config import config
from puregym_bot.puregym.client import PureGymClient
from puregym_bot.storage.db import get_db_session
from puregym_bot.storage.repository import get_all_users, get_user_by_telegram_id


async def on_startup(app):
    with get_db_session() as session:
        users = get_all_users(session)

    clients = dict[int, PureGymClient]()

    for user in users:
        config_user = next((u for u in config.users if u.telegram_id == user.telegram_id), None)
        if config_user is None:
            raise ValueError(f"User with telegram_id {user.telegram_id} exists in DB but not in config")
        clients[user.telegram_id] = PureGymClient(
            config_user.puregym_username, config_user.puregym_password.get_secret_value()
        )
        # await clients[user.telegram_id].login()
    app.bot_data["puregym_clients"] = clients


async def on_shutdown(app):
    clients = app.bot_data.get("puregym_clients")
    if clients is not None:
        for client in clients.values():
            await client.aclose()


AUTH_FILTER = filters.User([u.telegram_id for u in config.users])


def require_client(handler):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user is None:
            return
        with get_db_session() as session:
            user = get_user_by_telegram_id(session, update.effective_user.id)

        clients = context.bot_data["puregym_clients"]
        client = cast(PureGymClient, clients[update.effective_user.id])
        return await handler(update, context, client, user)

    return wrapper
