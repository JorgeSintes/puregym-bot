from dataclasses import dataclass
from typing import Awaitable, Callable, cast

from sqlmodel import Session
from telegram import Update
from telegram.ext import ContextTypes, filters

from puregym_bot.config import config
from puregym_bot.puregym.client import PureGymClient
from puregym_bot.storage.db import get_db_session
from puregym_bot.storage.repository import get_bot_state

AUTH_FILTER = filters.User([config.telegram_id])


@dataclass
class HandlerContext:
    session: Session
    client: PureGymClient
    bot_active: bool


async def on_startup(app):
    app.bot_data["puregym_client"] = PureGymClient(
        config.puregym_username,
        config.puregym_password.get_secret_value(),
    )


async def on_shutdown(app):
    client = cast(PureGymClient | None, app.bot_data.get("puregym_client"))
    if client is not None:
        await client.aclose()


def build_handler(
    handler: Callable[[Update, ContextTypes.DEFAULT_TYPE, HandlerContext], Awaitable[None]],
    *,
    allow_inactive: bool = False,
):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user is None or update.effective_chat is None:
            return
        if update.effective_user.id != config.telegram_id:
            return
        with get_db_session() as session:
            bot_state = get_bot_state(session)
            if not allow_inactive and bot_state.is_active is False:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=(
                        f"Hey {config.name}! Automatic booking is currently disabled. "
                        "Send /start to enable it again."
                    ),
                )
                return
            client = cast(PureGymClient, context.bot_data["puregym_client"])
            ctx = HandlerContext(session=session, client=client, bot_active=bot_state.is_active)
            return await handler(update, context, ctx)

    return wrapper
