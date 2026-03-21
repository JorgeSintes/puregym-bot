from types import SimpleNamespace
from typing import cast

import pytest
from sqlmodel import Session
from telegram import Update
from telegram.ext import ContextTypes

from puregym_bot.bot import dependencies
from puregym_bot.bot.registry import COMMANDS
from puregym_bot.storage.models import BotState


class RecordingBot:
    def __init__(self):
        self.calls: list[dict] = []

    async def send_message(self, *, chat_id: int, text: str, reply_markup=None):
        self.calls.append({"chat_id": chat_id, "text": text, "reply_markup": reply_markup})


def make_update():
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=1),
        effective_chat=SimpleNamespace(id=1),
    )


def make_context():
    return SimpleNamespace(bot=RecordingBot(), bot_data={"puregym_client": object()})


@pytest.mark.asyncio
async def test_build_handler_blocks_booking_commands_while_inactive(
    configured_jobs, session_factory, test_engine, monkeypatch
):
    with Session(test_engine, expire_on_commit=False) as session:
        session.add(BotState(id=1, is_active=False))
        session.commit()

    monkeypatch.setattr(dependencies, "get_db_session", session_factory)
    called = False

    async def handler(update, context, ctx):
        nonlocal called
        called = True

    wrapped = dependencies.build_handler(handler)
    context = make_context()

    await wrapped(
        cast(Update, make_update()),
        cast(ContextTypes.DEFAULT_TYPE, context),
    )

    assert called is False
    assert len(context.bot.calls) == 1
    assert "Automatic booking is currently disabled" in context.bot.calls[0]["text"]


@pytest.mark.asyncio
async def test_build_handler_allows_informational_commands_while_inactive(
    configured_jobs, session_factory, test_engine, monkeypatch
):
    with Session(test_engine, expire_on_commit=False) as session:
        session.add(BotState(id=1, is_active=False))
        session.commit()

    monkeypatch.setattr(dependencies, "get_db_session", session_factory)
    seen_bot_active: bool | None = None

    async def handler(update, context, ctx):
        nonlocal seen_bot_active
        seen_bot_active = ctx.bot_active

    wrapped = dependencies.build_handler(handler, allow_inactive=True)
    context = make_context()

    await wrapped(
        cast(Update, make_update()),
        cast(ContextTypes.DEFAULT_TYPE, context),
    )

    assert seen_bot_active is False
    assert context.bot.calls == []


def test_manage_bookings_command_is_registered_and_informational():
    command = next(spec for spec in COMMANDS if spec.name == "manage_bookings")

    assert command.description == "Review and manage upcoming bookings"
    assert command.allow_inactive is True
