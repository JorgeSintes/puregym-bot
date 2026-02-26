from dataclasses import dataclass
from typing import Awaitable, Callable, cast

from sqlmodel import Session
from telegram import Update
from telegram.ext import ContextTypes, filters

from puregym_bot.config import config
from puregym_bot.puregym.client import PureGymClient
from puregym_bot.storage.db import get_db_session
from puregym_bot.storage.models import User
from puregym_bot.storage.repository import get_all_users, get_user_by_telegram_id

AUTH_FILTER = filters.User([u.telegram_id for u in config.users])


@dataclass
class HandlerContext:
    session: Session
    client: PureGymClient
    user: User


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


def build_handler(
    handler: Callable[[Update, ContextTypes.DEFAULT_TYPE, HandlerContext], Awaitable[None]],
    *,
    allow_inactive: bool = False,
):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user is None or update.effective_chat is None:
            return
        with get_db_session() as session:
            user = cast(User, get_user_by_telegram_id(session, update.effective_user.id))
            if user is None:
                return
            if not allow_inactive and user.is_active is False:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"Hey {user.name}! You are currently inactive. Please send /start to activate the bot.",
                )
                return
            clients = context.bot_data["puregym_clients"]
            client = cast(PureGymClient, clients[update.effective_user.id])
            ctx = HandlerContext(session=session, client=client, user=user)
            return await handler(update, context, ctx)

    return wrapper
