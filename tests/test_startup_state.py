from types import SimpleNamespace

import pytest
from sqlmodel import Session, SQLModel, create_engine

from puregym_bot.bot import dependencies
from puregym_bot.storage import db as storage_db
from puregym_bot.storage.models import BotState
from puregym_bot.storage.repository import get_bot_state


class FakeClient:
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password


class RecordingBot:
    def __init__(self):
        self.calls: list[dict] = []

    async def send_message(self, *, chat_id: int, text: str, reply_markup=None):
        self.calls.append({"chat_id": chat_id, "text": text, "reply_markup": reply_markup})


@pytest.mark.asyncio
async def test_on_startup_sends_message_when_bot_is_active(
    configured_jobs, session_factory, test_config, monkeypatch
):
    monkeypatch.setattr(dependencies, "get_db_session", session_factory)
    monkeypatch.setattr(dependencies, "PureGymClient", FakeClient)

    app = SimpleNamespace(bot=RecordingBot(), bot_data={})

    await dependencies.on_startup(app)

    assert isinstance(app.bot_data["puregym_client"], FakeClient)
    assert len(app.bot.calls) == 1
    assert app.bot.calls[0]["chat_id"] == test_config.telegram_id
    assert "booking cycle" in app.bot.calls[0]["text"]
    assert "/stop" in app.bot.calls[0]["text"]


@pytest.mark.asyncio
async def test_on_startup_skips_message_when_bot_is_inactive(
    configured_jobs, session_factory, test_engine, monkeypatch
):
    with Session(test_engine, expire_on_commit=False) as session:
        state = session.get(BotState, 1)
        if state is None:
            state = BotState(id=1, is_active=False)
        else:
            state.is_active = False
        session.add(state)
        session.commit()

    monkeypatch.setattr(dependencies, "get_db_session", session_factory)
    monkeypatch.setattr(dependencies, "PureGymClient", FakeClient)

    app = SimpleNamespace(bot=RecordingBot(), bot_data={})

    await dependencies.on_startup(app)

    assert isinstance(app.bot_data["puregym_client"], FakeClient)
    assert app.bot.calls == []


def test_get_bot_state_creates_enabled_state_by_default(configured_jobs, session_factory):
    with session_factory() as session:
        state = get_bot_state(session)

        assert state.is_active is True


def test_init_db_preserves_existing_bot_state(monkeypatch):
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(BotState(id=1, is_active=False))
        session.commit()

    monkeypatch.setattr(storage_db, "engine", engine)

    storage_db.init_db()

    with Session(engine) as session:
        state = session.get(BotState, 1)

    assert state is not None
    assert state.is_active is False


def test_init_db_creates_enabled_bot_state_when_missing(monkeypatch):
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)

    monkeypatch.setattr(storage_db, "engine", engine)

    storage_db.init_db()

    with Session(engine) as session:
        state = session.get(BotState, 1)

    assert state is not None
    assert state.is_active is True
