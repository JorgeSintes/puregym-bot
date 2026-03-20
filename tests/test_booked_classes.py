from datetime import datetime, time
from types import SimpleNamespace
from typing import cast

import pytest
from sqlmodel import Session
from telegram import Update
from telegram.ext import ContextTypes

from puregym_bot.bot.dependencies import HandlerContext
from puregym_bot.bot.handlers import booked_classes
from puregym_bot.puregym.client import PureGymClient
from puregym_bot.storage.models import BookingStatus, ManagedBooking
from tests.fakes import FakeContext, FakePureGymClient, make_gym_class


def make_update():
    return cast(
        Update,
        SimpleNamespace(
            effective_user=SimpleNamespace(id=1),
            effective_chat=SimpleNamespace(id=1),
        ),
    )


def test_gym_class_waitlist_helpers_parse_booked_waitlist_position():
    gym_class = make_gym_class(
        booking_id="b-1",
        activity_id=1,
        day=datetime(2026, 3, 23).date(),
        start=time(16, 30),
        end=time(17, 25),
        participation_id="pid-1",
        button={"description": "Du er nr. 40 på ventelisten"},
    )

    assert gym_class.button_description == "Du er nr. 40 på ventelisten"
    assert gym_class.waitlist_position == 40
    assert gym_class.waitlist_size is None
    assert gym_class.is_waitlisted is True


def test_gym_class_waitlist_helpers_parse_open_waitlist_size():
    gym_class = make_gym_class(
        booking_id="b-2",
        activity_id=2,
        day=datetime(2026, 3, 23).date(),
        start=time(17, 30),
        end=time(18, 25),
        participation_id=None,
        button={"description": "Venteliste (21)"},
    )

    assert gym_class.waitlist_position is None
    assert gym_class.waitlist_size == 21
    assert gym_class.is_waitlisted is True


def test_gym_class_waitlist_helpers_ignore_missing_description():
    gym_class = make_gym_class(
        booking_id="b-3",
        activity_id=3,
        day=datetime(2026, 3, 23).date(),
        start=time(9, 0),
        end=time(9, 55),
        participation_id="pid-3",
    )

    assert gym_class.button_description is None
    assert gym_class.waitlist_position is None
    assert gym_class.waitlist_size is None
    assert gym_class.is_waitlisted is False


def test_gym_class_format_uses_telegram_date_time_format():
    gym_class = make_gym_class(
        booking_id="b-4",
        activity_id=4,
        day=datetime(2026, 3, 23).date(),
        start=time(9, 0),
        end=time(9, 55),
        participation_id="pid-4",
    )

    assert gym_class.format() == "Body Pump on Mon 23/03 09:00 (Main Hall) | cancel by Mon 23/03 06:00"


@pytest.mark.asyncio
async def test_booked_classes_shows_managed_status_and_waitlist_position(configured_jobs, test_engine):
    live_classes = [
        make_gym_class(
            booking_id="b-accepted",
            activity_id=1,
            day=datetime(2026, 3, 23).date(),
            start=time(9, 0),
            end=time(9, 55),
            participation_id="pid-accepted",
            title="Bike Standard",
            location="PureGym Aarhusgade",
        ),
        make_gym_class(
            booking_id="b-pending",
            activity_id=2,
            day=datetime(2026, 3, 23).date(),
            start=time(16, 30),
            end=time(17, 25),
            participation_id="pid-pending",
            title="Bike Power",
            location="PureGym Aarhusgade",
            button={"description": "Du er nr. 40 på ventelisten"},
        ),
    ]
    client = FakePureGymClient(live_classes)
    context = FakeContext(client)

    with Session(test_engine, expire_on_commit=False) as session:
        session.add(
            ManagedBooking(
                booking_id="b-accepted",
                activity_id=1,
                payment_type="membership",
                participation_id="pid-accepted",
                class_datetime=datetime(2026, 3, 23, 9, 0),
                status=BookingStatus.CONFIRMED,
            )
        )
        session.add(
            ManagedBooking(
                booking_id="b-pending",
                activity_id=2,
                payment_type="membership",
                participation_id="pid-pending",
                class_datetime=datetime(2026, 3, 23, 16, 30),
                status=BookingStatus.PENDING,
            )
        )
        session.commit()

        handler_ctx = HandlerContext(session=session, client=cast(PureGymClient, client), bot_active=True)
        await booked_classes(make_update(), cast(ContextTypes.DEFAULT_TYPE, context), handler_ctx)

    assert len(context.bot.calls) == 1
    assert context.bot.calls[0]["text"] == (
        "Your upcoming bookings:\n"
        "- Bike Standard - Mon 23/03 09:00 - PureGym Aarhusgade - confirmed\n"
        "- Bike Power - Mon 23/03 16:30 - PureGym Aarhusgade - pending - waitlist #40"
    )


@pytest.mark.asyncio
async def test_booked_classes_hides_stale_managed_bookings(configured_jobs, test_engine):
    live_classes = [
        make_gym_class(
            booking_id="b-managed",
            activity_id=1,
            day=datetime(2026, 3, 23).date(),
            start=time(9, 0),
            end=time(9, 55),
            participation_id="pid-managed",
            title="Bike Standard",
            location="PureGym Aarhusgade",
        ),
        make_gym_class(
            booking_id="b-unmanaged",
            activity_id=2,
            day=datetime(2026, 3, 23).date(),
            start=time(12, 0),
            end=time(12, 55),
            participation_id="pid-unmanaged",
            title="Yoga Flow",
            location="PureGym Aarhusgade",
            button={"description": "Du er nr. 7 på ventelisten"},
        ),
    ]
    client = FakePureGymClient(live_classes)
    context = FakeContext(client)

    with Session(test_engine, expire_on_commit=False) as session:
        session.add(
            ManagedBooking(
                booking_id="b-managed",
                activity_id=1,
                payment_type="membership",
                participation_id="pid-managed",
                class_datetime=datetime(2026, 3, 23, 9, 0),
                status=BookingStatus.PENDING,
            )
        )
        session.commit()

        handler_ctx = HandlerContext(session=session, client=cast(PureGymClient, client), bot_active=True)
        await booked_classes(make_update(), cast(ContextTypes.DEFAULT_TYPE, context), handler_ctx)

    assert len(context.bot.calls) == 1
    assert context.bot.calls[0]["text"] == (
        "Your upcoming bookings:\n"
        "- Bike Standard - Mon 23/03 09:00 - PureGym Aarhusgade - pending\n"
        "- Yoga Flow - Mon 23/03 12:00 - PureGym Aarhusgade - unmanaged - waitlist #7"
    )


@pytest.mark.asyncio
async def test_booked_classes_returns_no_upcoming_bookings_when_live_list_is_empty(
    configured_jobs, test_engine
):
    client = FakePureGymClient([])
    context = FakeContext(client)

    with Session(test_engine, expire_on_commit=False) as session:
        session.add(
            ManagedBooking(
                booking_id="b-stale",
                activity_id=1,
                payment_type="membership",
                participation_id="pid-stale",
                class_datetime=datetime(2026, 3, 23, 9, 0),
                status=BookingStatus.PENDING,
            )
        )
        session.commit()

        handler_ctx = HandlerContext(session=session, client=cast(PureGymClient, client), bot_active=True)
        await booked_classes(make_update(), cast(ContextTypes.DEFAULT_TYPE, context), handler_ctx)

    assert len(context.bot.calls) == 1
    assert context.bot.calls[0]["text"] == "You have no upcoming bookings."


@pytest.mark.asyncio
async def test_booked_classes_splits_long_output_into_multiple_messages(configured_jobs, test_engine):
    live_classes = []
    with Session(test_engine, expire_on_commit=False) as session:
        for idx in range(70):
            booking_id = f"b-{idx}"
            participation_id = f"pid-{idx}"
            live_classes.append(
                make_gym_class(
                    booking_id=booking_id,
                    activity_id=idx,
                    day=datetime(2026, 3, 23).date(),
                    start=time(9 + (idx % 10), idx % 60),
                    end=time(10 + (idx % 10), idx % 60),
                    participation_id=participation_id,
                    title=f"Very Long Class Name {idx} {'X' * 40}",
                    location=f"PureGym Aarhusgade {'Y' * 30}",
                )
            )
            session.add(
                ManagedBooking(
                    booking_id=booking_id,
                    activity_id=idx,
                    payment_type="membership",
                    participation_id=participation_id,
                    class_datetime=datetime(2026, 3, 23, 9 + (idx % 10), idx % 60),
                    status=BookingStatus.PENDING,
                )
            )
        session.commit()

        client = FakePureGymClient(live_classes)
        context = FakeContext(client)
        handler_ctx = HandlerContext(session=session, client=cast(PureGymClient, client), bot_active=True)
        await booked_classes(make_update(), cast(ContextTypes.DEFAULT_TYPE, context), handler_ctx)

    assert len(context.bot.calls) > 1
    assert context.bot.calls[0]["text"].startswith("Your upcoming bookings:\n")
    assert all(len(call["text"]) <= 4000 for call in context.bot.calls)
