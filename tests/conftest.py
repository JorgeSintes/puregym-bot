from contextlib import contextmanager
from datetime import time

import pytest
from sqlmodel import Session, SQLModel, create_engine

from puregym_bot.bot import jobs
from puregym_bot.config import GymClassPreferences, TimeSlot, Weekday, config
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
def configured_jobs(monkeypatch, session_factory):
    monkeypatch.setattr(jobs, "get_db_session", session_factory)
    monkeypatch.setattr(config, "telegram_id", 1)
    monkeypatch.setattr(config, "max_bookings", 10)
    monkeypatch.setattr(config, "max_days_in_advance", 28)
    monkeypatch.setattr(config, "booking_reminder_hours", 24)
    monkeypatch.setattr(config, "pending_auto_cancel_hours", 3)
    monkeypatch.setattr(
        config,
        "class_preferences",
        GymClassPreferences(
            interested_classes=[101, 102, 103],
            interested_centers=[1],
            available_time_slots=[
                TimeSlot(day_of_week=Weekday.MONDAY, start_time=time(17, 0), end_time=time(22, 0)),
                TimeSlot(day_of_week=Weekday.TUESDAY, start_time=time(17, 0), end_time=time(22, 0)),
            ],
        ),
    )


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
