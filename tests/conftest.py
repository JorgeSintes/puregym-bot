from contextlib import contextmanager
from datetime import time

import pytest
from pydantic import SecretStr
from sqlmodel import Session, SQLModel, create_engine

from puregym_bot.bot import app, booking_cycle, dependencies, handlers
from puregym_bot.config import Config, GymClassPreferences, TimeSlot, Weekday, clear_config_cache
from puregym_bot.puregym import client as puregym_client
from puregym_bot.storage.models import BotState


@pytest.fixture
def test_engine():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def session_factory(test_engine):
    @contextmanager
    def _session_factory():
        with Session(test_engine, expire_on_commit=False) as session:
            yield session

    return _session_factory


@pytest.fixture
def configured_jobs(monkeypatch, session_factory, test_config):
    monkeypatch.setattr(booking_cycle, "get_db_session", session_factory)
    monkeypatch.setattr(app, "get_config", lambda: test_config)
    monkeypatch.setattr(booking_cycle, "get_config", lambda: test_config)
    monkeypatch.setattr(dependencies, "get_config", lambda: test_config)
    monkeypatch.setattr(handlers, "get_config", lambda: test_config)
    monkeypatch.setattr(puregym_client, "get_config", lambda: test_config)


@pytest.fixture
def test_config():
    return Config.model_construct(
        telegram_token=SecretStr("test-token"),
        name="Test User",
        telegram_id=1,
        puregym_username="test-user",
        puregym_password=SecretStr("test-password"),
        class_preferences=GymClassPreferences(
            interested_classes=[101, 102, 103],
            interested_centers=[1],
            available_time_slots=[
                TimeSlot(day_of_week=Weekday.MONDAY, start_time=time(17, 0), end_time=time(22, 0)),
                TimeSlot(day_of_week=Weekday.TUESDAY, start_time=time(17, 0), end_time=time(22, 0)),
            ],
        ),
        logging_level="INFO",
        max_bookings=10,
        max_days_in_advance=28,
        booking_reminder_hours=24,
        pending_auto_cancel_hours=3,
    )


@pytest.fixture(autouse=True)
def reset_config_cache():
    clear_config_cache()
    yield
    clear_config_cache()


@pytest.fixture
def activate_bot(session_factory):
    with session_factory() as session:
        state = session.get(BotState, 1)
        if state is None:
            state = BotState(id=1, is_active=True)
            session.add(state)
        else:
            state.is_active = True
            session.add(state)
        session.commit()
