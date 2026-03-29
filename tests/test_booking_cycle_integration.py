from datetime import date, datetime, timedelta
from typing import cast

import pytest
import time_machine
from sqlmodel import Session, select
from telegram.ext import ContextTypes

from puregym_bot.bot.booking_cycle import run_booking_cycle
from puregym_bot.storage.models import BookingStatus, BotState, ManagedBooking
from tests.fakes import FakeContext, FakePureGymClient, make_gym_class


@pytest.mark.asyncio
async def test_run_booking_cycle_full_chain(configured_jobs, session_factory, test_engine):
    now = datetime(2026, 3, 23, 17, 0, 0)
    monday = date(2026, 3, 23)
    tuesday = date(2026, 3, 24)

    booked_manual = make_gym_class(
        booking_id="b-manual",
        activity_id=1,
        day=monday,
        start=datetime(2026, 3, 23, 18, 0).time(),
        end=datetime(2026, 3, 23, 19, 0).time(),
        participation_id="pid-manual",
    )
    booked_pending = make_gym_class(
        booking_id="b-pending",
        activity_id=2,
        day=monday,
        start=datetime(2026, 3, 23, 19, 0).time(),
        end=datetime(2026, 3, 23, 20, 0).time(),
        participation_id="pid-pending",
    )
    booked_confirmed = make_gym_class(
        booking_id="b-confirmed",
        activity_id=3,
        day=monday,
        start=datetime(2026, 3, 23, 20, 0).time(),
        end=datetime(2026, 3, 23, 21, 0).time(),
        participation_id="pid-confirmed",
    )
    available_single = make_gym_class(
        booking_id="b-single",
        activity_id=4,
        day=tuesday,
        start=datetime(2026, 3, 24, 18, 0).time(),
        end=datetime(2026, 3, 24, 19, 0).time(),
        participation_id=None,
    )
    available_option1 = make_gym_class(
        booking_id="b-opt-1",
        activity_id=5,
        day=monday,
        start=datetime(2026, 3, 23, 19, 0).time(),
        end=datetime(2026, 3, 23, 20, 0).time(),
        participation_id=None,
    )
    available_option2 = make_gym_class(
        booking_id="b-opt-2",
        activity_id=6,
        day=monday,
        start=datetime(2026, 3, 23, 19, 15).time(),
        end=datetime(2026, 3, 23, 20, 15).time(),
        participation_id=None,
    )

    client = FakePureGymClient(
        [
            booked_manual,
            booked_pending,
            booked_confirmed,
            available_single,
            available_option1,
            available_option2,
        ]
    )
    context = FakeContext(client)

    with Session(test_engine, expire_on_commit=False) as session:
        session.add(BotState(id=1, is_active=True))
        session.add(
            ManagedBooking(
                booking_id="b-pending",
                activity_id=2,
                payment_type="membership",
                participation_id="pid-pending",
                class_title="Body Pump",
                class_location="Main Hall",
                class_datetime=now + timedelta(hours=2),
                status=BookingStatus.PENDING,
                reminder_sent=False,
            )
        )
        session.add(
            ManagedBooking(
                booking_id="b-confirmed",
                activity_id=3,
                payment_type="membership",
                participation_id="pid-confirmed",
                class_title="Body Pump",
                class_location="Main Hall",
                class_datetime=now + timedelta(hours=2),
                status=BookingStatus.CONFIRMED,
                reminder_sent=False,
            )
        )
        session.commit()

    with time_machine.travel(now, tick=False):
        await run_booking_cycle(cast(ContextTypes.DEFAULT_TYPE, context))

    with session_factory() as session:
        pending = session.exec(
            select(ManagedBooking).where(ManagedBooking.participation_id == "pid-pending")
        ).first()
        confirmed = session.exec(
            select(ManagedBooking).where(ManagedBooking.participation_id == "pid-confirmed")
        ).first()
        manual = session.exec(
            select(ManagedBooking).where(ManagedBooking.participation_id == "pid-manual")
        ).first()
        new_single = session.exec(
            select(ManagedBooking).where(ManagedBooking.participation_id == "p-b-single")
        ).first()

        assert pending is not None
        assert confirmed is not None
        assert manual is not None
        assert new_single is not None

        assert pending.status == BookingStatus.CANCELLED
        assert confirmed.reminder_sent is True
        assert manual.status == BookingStatus.CANCELLED
        assert new_single.status == BookingStatus.PENDING

    assert ("b-single", 4, "membership") in client.book_by_ids_calls
    assert "pid-pending" in client.unbook_calls
    texts = [call["text"] for call in context.bot.calls]
    assert any("Found a booking not tracked by the bot" in text for text in texts)
    assert any("Booked:" in text for text in texts)
    assert not any("Multiple classes match this time slot" in text for text in texts)
    assert any(
        "Reminder: your class is coming up soon.\nMon 23/03 19:00  Body Pump @ Main Hall\n"
        "If you changed your mind, cancel now or revert to pending to reconsider." == text
        for text in texts
    )
    assert any("Pending booking was cancelled" in text for text in texts)


@pytest.mark.asyncio
async def test_run_booking_cycle_skips_when_inactive(configured_jobs, test_engine):
    client = FakePureGymClient([])
    context = FakeContext(client)

    with Session(test_engine, expire_on_commit=False) as session:
        state = session.get(BotState, 1)
        if state is None:
            state = BotState(id=1, is_active=False)
        else:
            state.is_active = False
        session.add(state)
        session.commit()

    await run_booking_cycle(cast(ContextTypes.DEFAULT_TYPE, context))

    assert context.bot.calls == []
    assert client.book_calls == []
    assert client.unbook_calls == []
