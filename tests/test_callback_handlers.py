from datetime import datetime
from types import SimpleNamespace
from typing import cast

import pytest
from sqlmodel import Session, select
from telegram import Update
from telegram.ext import ContextTypes
from puregym_bot.bot import handlers
from puregym_bot.bot.callback_data import BookingCallback, BookingCallbackAction, ChoicePickCallback
from puregym_bot.storage.models import BookingChoice, BookingStatus, ManagedBooking
from tests.fakes import FakeContext, FakePureGymClient


class FakeCallbackQuery:
    def __init__(self, data: str):
        self.data = data
        self.answered = False
        self.edited_texts: list[str] = []

    async def answer(self):
        self.answered = True

    async def edit_message_text(self, *, text: str):
        self.edited_texts.append(text)


def make_update(callback_query: FakeCallbackQuery):
    return cast(
        Update,
        SimpleNamespace(
            effective_user=SimpleNamespace(id=1),
            callback_query=callback_query,
        ),
    )


@pytest.mark.asyncio
async def test_button_accept_callback_confirms_pending_booking(
    configured_jobs, session_factory, test_engine, monkeypatch
):
    monkeypatch.setattr(handlers, "get_db_session", session_factory)

    with Session(test_engine, expire_on_commit=False) as session:
        booking = ManagedBooking(
            booking_id="b-1",
            activity_id=1,
            payment_type="membership",
            participation_id="pid-1",
            class_title="Body Pump",
            class_location="Main Hall",
            class_datetime=datetime(2026, 3, 23, 18, 0),
            status=BookingStatus.PENDING,
        )
        session.add(booking)
        session.commit()

    callback_query = FakeCallbackQuery(
        BookingCallback(
            action=BookingCallbackAction.ACCEPT,
            participation_id="pid-1",
        ).to_callback_data()
    )
    context = FakeContext(FakePureGymClient([]))

    await handlers.button(make_update(callback_query), cast(ContextTypes.DEFAULT_TYPE, context))

    with Session(test_engine, expire_on_commit=False) as session:
        refreshed = session.exec(select(ManagedBooking)).one()

    assert callback_query.answered is True
    assert callback_query.edited_texts == ["Booking accepted."]
    assert refreshed.status == BookingStatus.CONFIRMED


@pytest.mark.asyncio
async def test_button_cancel_callback_unbooks_and_cancels_booking(
    configured_jobs, session_factory, test_engine, monkeypatch
):
    monkeypatch.setattr(handlers, "get_db_session", session_factory)

    with Session(test_engine, expire_on_commit=False) as session:
        booking = ManagedBooking(
            booking_id="b-2",
            activity_id=2,
            payment_type="membership",
            participation_id="pid-2",
            class_title="Yin Yoga",
            class_location="Studio 2",
            class_datetime=datetime(2099, 3, 23, 18, 0),
            status=BookingStatus.CONFIRMED,
        )
        session.add(booking)
        session.commit()

    client = FakePureGymClient([])
    callback_query = FakeCallbackQuery(
        BookingCallback(
            action=BookingCallbackAction.CANCEL,
            participation_id="pid-2",
        ).to_callback_data()
    )
    context = FakeContext(client)

    await handlers.button(make_update(callback_query), cast(ContextTypes.DEFAULT_TYPE, context))

    with Session(test_engine, expire_on_commit=False) as session:
        refreshed = session.exec(select(ManagedBooking)).one()

    assert callback_query.edited_texts == ["Booking cancelled."]
    assert client.unbook_calls == ["pid-2"]
    assert refreshed.status == BookingStatus.CANCELLED


@pytest.mark.asyncio
async def test_button_revert_pending_callback_reverts_confirmed_to_pending(
    configured_jobs, session_factory, test_engine, monkeypatch
):
    monkeypatch.setattr(handlers, "get_db_session", session_factory)

    with Session(test_engine, expire_on_commit=False) as session:
        booking = ManagedBooking(
            booking_id="b-3",
            activity_id=3,
            payment_type="membership",
            participation_id="pid-3",
            class_title="Spin Class",
            class_location="Studio 1",
            class_datetime=datetime(2099, 3, 23, 18, 0),
            status=BookingStatus.CONFIRMED,
            reminder_sent=True,
        )
        session.add(booking)
        session.commit()

    callback_query = FakeCallbackQuery(
        BookingCallback(
            action=BookingCallbackAction.REVERT_PENDING,
            participation_id="pid-3",
        ).to_callback_data()
    )
    context = FakeContext(FakePureGymClient([]))

    await handlers.button(make_update(callback_query), cast(ContextTypes.DEFAULT_TYPE, context))

    with Session(test_engine, expire_on_commit=False) as session:
        refreshed = session.exec(select(ManagedBooking)).one()

    assert callback_query.answered is True
    assert callback_query.edited_texts == ["Booking reverted to pending."]
    assert refreshed.status == BookingStatus.PENDING
    assert refreshed.reminder_sent is False


@pytest.mark.asyncio
async def test_button_cancel_callback_blocks_within_two_hour_window(
    configured_jobs, session_factory, test_engine, monkeypatch
):
    monkeypatch.setattr(handlers, "get_db_session", session_factory)

    with Session(test_engine, expire_on_commit=False) as session:
        booking = ManagedBooking(
            booking_id="b-close",
            activity_id=4,
            payment_type="membership",
            participation_id="pid-close",
            class_title="Hot Yoga",
            class_location="Studio 3",
            class_datetime=datetime(2026, 3, 29, 12, 0),
            status=BookingStatus.CONFIRMED,
        )
        session.add(booking)
        session.commit()

    client = FakePureGymClient([])
    callback_query = FakeCallbackQuery(
        BookingCallback(
            action=BookingCallbackAction.CANCEL,
            participation_id="pid-close",
        ).to_callback_data()
    )
    context = FakeContext(client)

    await handlers.button(make_update(callback_query), cast(ContextTypes.DEFAULT_TYPE, context))

    with Session(test_engine, expire_on_commit=False) as session:
        refreshed = session.exec(select(ManagedBooking)).one()

    assert callback_query.edited_texts == ["This booking can no longer be cancelled."]
    assert client.unbook_calls == []
    assert refreshed.status == BookingStatus.CONFIRMED


@pytest.mark.asyncio
async def test_button_revert_callback_blocks_within_two_hour_window(
    configured_jobs, session_factory, test_engine, monkeypatch
):
    monkeypatch.setattr(handlers, "get_db_session", session_factory)

    with Session(test_engine, expire_on_commit=False) as session:
        booking = ManagedBooking(
            booking_id="b-revert-close",
            activity_id=5,
            payment_type="membership",
            participation_id="pid-revert-close",
            class_title="Pilates",
            class_location="Studio 4",
            class_datetime=datetime(2026, 3, 29, 12, 0),
            status=BookingStatus.CONFIRMED,
            reminder_sent=True,
        )
        session.add(booking)
        session.commit()

    callback_query = FakeCallbackQuery(
        BookingCallback(
            action=BookingCallbackAction.REVERT_PENDING,
            participation_id="pid-revert-close",
        ).to_callback_data()
    )
    context = FakeContext(FakePureGymClient([]))

    await handlers.button(make_update(callback_query), cast(ContextTypes.DEFAULT_TYPE, context))

    with Session(test_engine, expire_on_commit=False) as session:
        refreshed = session.exec(select(ManagedBooking)).one()

    assert callback_query.edited_texts == ["This booking can no longer be cancelled."]
    assert refreshed.status == BookingStatus.CONFIRMED
    assert refreshed.reminder_sent is True


@pytest.mark.asyncio
async def test_button_pick_callback_books_selection_and_sends_follow_up_prompt(
    configured_jobs, session_factory, test_engine, monkeypatch
):
    monkeypatch.setattr(handlers, "get_db_session", session_factory)

    with Session(test_engine, expire_on_commit=False) as session:
        choice = BookingChoice(
            slot_date="2026-03-23",
            slot_start="17:00:00",
            slot_end="22:00:00",
            options_json=(
                '[{"booking_id": "b-3", "activity_id": 3, "payment_type": "membership", '
                '"title": "Body Pump", "date": "2026-03-23", "start_time": "18:00:00", '
                '"location": "Main Hall"}]'
            ),
        )
        session.add(choice)
        session.commit()
        choice_id = choice.id

    assert choice_id is not None
    client = FakePureGymClient([])
    context = FakeContext(client)
    callback_query = FakeCallbackQuery(
        ChoicePickCallback(choice_id=choice_id, option_index=0).to_callback_data()
    )

    await handlers.button(make_update(callback_query), cast(ContextTypes.DEFAULT_TYPE, context))

    with Session(test_engine, expire_on_commit=False) as session:
        bookings = list(session.exec(select(ManagedBooking)).all())
        refreshed_choice = session.get(BookingChoice, choice_id)

    assert callback_query.edited_texts == ["Booked your selection. Please accept or reject."]
    assert client.book_by_ids_calls == [("b-3", 3, "membership")]
    assert len(bookings) == 1
    assert bookings[0].participation_id == "p-b-3"
    assert refreshed_choice is not None
    assert refreshed_choice.status.value == "handled"
    assert context.bot.calls[0]["text"].startswith("Booked: Mon 23/03 18:00  Body Pump @ Main Hall")


@pytest.mark.asyncio
async def test_button_rejects_unknown_callback_payload(configured_jobs):
    callback_query = FakeCallbackQuery("bad:data")
    context = FakeContext(FakePureGymClient([]))

    await handlers.button(make_update(callback_query), cast(ContextTypes.DEFAULT_TYPE, context))

    assert callback_query.answered is True
    assert callback_query.edited_texts == ["This action is no longer available."]
