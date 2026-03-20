from datetime import date, datetime, time, timedelta
from typing import cast

import pytest
from sqlmodel import Session, select

from puregym_bot.bot import booking_cycle
from puregym_bot.bot.callback_data import BookingCallback, BookingCallbackAction
from puregym_bot.puregym.client import PureGymClient
from puregym_bot.storage.models import BookingChoice, BookingStatus, BotState, ManagedBooking
from tests.fakes import FakePureGymClient, make_gym_class


def test_is_cycle_active_respects_bot_state(configured_jobs, test_engine):
    with Session(test_engine, expire_on_commit=False) as session:
        session.add(BotState(id=1, is_active=False))
        session.commit()
        assert booking_cycle.is_cycle_active(session) is False

        state = session.get(BotState, 1)
        assert state is not None
        state.is_active = True
        session.add(state)
        session.commit()
        assert booking_cycle.is_cycle_active(session) is True


def test_reconcile_bookings_missing_in_puregym(configured_jobs, test_engine):
    now = datetime(2026, 3, 20, 18, 0, 0)

    with Session(test_engine, expire_on_commit=False) as session:
        past_confirmed = ManagedBooking(
            booking_id="b-past",
            activity_id=1,
            payment_type="membership",
            participation_id="pid-past",
            class_datetime=now - timedelta(hours=1),
            status=BookingStatus.CONFIRMED,
        )
        future_pending = ManagedBooking(
            booking_id="b-future",
            activity_id=2,
            payment_type="membership",
            participation_id="pid-future",
            class_datetime=now + timedelta(hours=2),
            status=BookingStatus.PENDING,
        )
        session.add(past_confirmed)
        session.add(future_pending)
        session.commit()

        result = booking_cycle.reconcile_bookings_missing_in_puregym(
            session, booked_by_participation={}, now=now
        )
        assert len(result.prompts) == 2

        refreshed_past = session.get(ManagedBooking, past_confirmed.id)
        refreshed_future = session.get(ManagedBooking, future_pending.id)
        assert refreshed_past is not None
        assert refreshed_future is not None
        assert refreshed_past.status == BookingStatus.ATTENDED
        assert refreshed_future.status == BookingStatus.CANCELLED


def test_import_untracked_bookings_creates_pending_and_prompt(configured_jobs, test_engine):
    day = date(2026, 3, 23)
    gym_class = make_gym_class(
        booking_id="b-manual",
        activity_id=11,
        day=day,
        start=time(18, 0),
        end=time(19, 0),
        participation_id="pid-manual",
    )

    with Session(test_engine, expire_on_commit=False) as session:
        result = booking_cycle.import_untracked_bookings(session, {"pid-manual": gym_class})
        assert len(result.prompts) == 1
        prompt = result.prompts[0]
        assert prompt.booking is not None
        assert prompt.booking.status == BookingStatus.PENDING
        assert "Do you want to keep it?" in prompt.message.text
        assert (
            prompt.message.buttons[0][0].callback_data
            == BookingCallback(
                action=BookingCallbackAction.ACCEPT,
                participation_id="pid-manual",
            ).to_callback_data()
        )


def test_detect_booking_state_mismatch_warns_and_prompts(configured_jobs, test_engine, caplog):
    now = datetime(2026, 3, 20, 18, 0, 0)
    gym_class = make_gym_class(
        booking_id="b-puregym",
        activity_id=12,
        day=date(2026, 3, 23),
        start=time(18, 0),
        end=time(19, 0),
        participation_id="pid-puregym",
    )

    with Session(test_engine, expire_on_commit=False) as session:
        session.add(
            ManagedBooking(
                booking_id="b-db",
                activity_id=13,
                payment_type="membership",
                participation_id="pid-db",
                class_datetime=now + timedelta(hours=2),
                status=BookingStatus.PENDING,
            )
        )
        session.commit()

        with caplog.at_level("WARNING"):
            result = booking_cycle.detect_booking_state_mismatch(session, {"pid-puregym": gym_class})

    assert len(result.prompts) == 1
    assert "Booking state mismatch detected after reconciliation" in result.prompts[0].message.text
    assert "DB-only participation IDs: pid-db" in result.prompts[0].message.text
    assert "PureGym-only participation IDs: pid-puregym" in result.prompts[0].message.text
    assert "Booking state mismatch detected after reconciliation" in caplog.text


def test_detect_booking_state_mismatch_is_silent_when_sets_match(configured_jobs, test_engine, caplog):
    now = datetime(2026, 3, 20, 18, 0, 0)
    gym_class = make_gym_class(
        booking_id="b-match",
        activity_id=14,
        day=date(2026, 3, 23),
        start=time(18, 0),
        end=time(19, 0),
        participation_id="pid-match",
    )

    with Session(test_engine, expire_on_commit=False) as session:
        session.add(
            ManagedBooking(
                booking_id="b-match",
                activity_id=14,
                payment_type="membership",
                participation_id="pid-match",
                class_datetime=now + timedelta(hours=2),
                status=BookingStatus.PENDING,
            )
        )
        session.commit()

        with caplog.at_level("WARNING"):
            result = booking_cycle.detect_booking_state_mismatch(session, {"pid-match": gym_class})

    assert result.prompts == []
    assert caplog.text == ""


@pytest.mark.asyncio
async def test_handle_slot_booking_actions_single_and_multiple(configured_jobs, test_engine):
    monday = date(2026, 3, 23)
    tuesday = date(2026, 3, 24)
    single = make_gym_class(
        booking_id="b-single",
        activity_id=21,
        day=monday,
        start=time(18, 0),
        end=time(19, 0),
        participation_id=None,
    )
    option1 = make_gym_class(
        booking_id="b-opt-1",
        activity_id=22,
        day=tuesday,
        start=time(18, 0),
        end=time(19, 0),
        participation_id=None,
    )
    option2 = make_gym_class(
        booking_id="b-opt-2",
        activity_id=23,
        day=tuesday,
        start=time(19, 0),
        end=time(20, 0),
        participation_id=None,
    )

    grouped = booking_cycle.group_by_slot(
        [single, option1, option2], booking_cycle.get_config().class_preferences.available_time_slots
    )
    client = FakePureGymClient([])

    with Session(test_engine, expire_on_commit=False) as session:
        result = await booking_cycle.handle_slot_booking_actions(
            session,
            cast(PureGymClient, client),
            grouped,
            active_count=0,
        )

        assert len(result.prompts) == 2
        booking_prompts = [p for p in result.prompts if p.booking is not None]
        choice_prompts = [p for p in result.prompts if p.choice is not None]
        assert len(booking_prompts) == 1
        assert len(choice_prompts) == 1

        all_bookings = list(session.exec(select(ManagedBooking)).all())
        all_choices = list(session.exec(select(BookingChoice)).all())
        assert len(all_bookings) == 1
        assert len(all_choices) == 1
        assert client.book_calls == ["b-single"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [BookingStatus.PENDING, BookingStatus.CONFIRMED, BookingStatus.CANCELLED],
)
async def test_handle_slot_booking_actions_skips_handled_slot(configured_jobs, test_engine, status):
    monday = date(2026, 3, 23)
    single = make_gym_class(
        booking_id="b-single",
        activity_id=24,
        day=monday,
        start=time(18, 0),
        end=time(19, 0),
        participation_id=None,
    )
    grouped = booking_cycle.group_by_slot(
        [single], booking_cycle.get_config().class_preferences.available_time_slots
    )
    client = FakePureGymClient([])

    with Session(test_engine, expire_on_commit=False) as session:
        session.add(
            ManagedBooking(
                booking_id="b-existing",
                activity_id=25,
                payment_type="membership",
                participation_id="pid-existing",
                class_datetime=datetime(2026, 3, 23, 18, 30),
                status=status,
            )
        )
        session.commit()

        result = await booking_cycle.handle_slot_booking_actions(
            session,
            cast(PureGymClient, client),
            grouped,
            active_count=0,
        )

        assert result.prompts == []
        assert client.book_calls == []
        all_bookings = list(session.exec(select(ManagedBooking)).all())
        assert len(all_bookings) == 1


@pytest.mark.asyncio
async def test_handle_slot_booking_actions_warns_and_skips_when_booked_class_has_no_blocking_record(
    configured_jobs, test_engine, caplog
):
    monday = date(2026, 3, 23)
    booked = make_gym_class(
        booking_id="b-booked",
        activity_id=26,
        day=monday,
        start=time(18, 0),
        end=time(19, 0),
        participation_id="pid-booked",
    )
    available = make_gym_class(
        booking_id="b-available",
        activity_id=27,
        day=monday,
        start=time(19, 0),
        end=time(20, 0),
        participation_id=None,
    )
    grouped = booking_cycle.group_by_slot(
        [booked, available], booking_cycle.get_config().class_preferences.available_time_slots
    )
    client = FakePureGymClient([])

    with Session(test_engine, expire_on_commit=False) as session:
        with caplog.at_level("WARNING"):
            result = await booking_cycle.handle_slot_booking_actions(
                session,
                cast(PureGymClient, client),
                grouped,
                active_count=0,
            )

    assert result.prompts == []
    assert client.book_calls == []
    assert "Skipping slot 2026-03-23 17:00:00-22:00:00 because booked classes were found" in caplog.text


def test_send_due_reminders_pending_and_confirmed_once(configured_jobs, test_engine):
    now = datetime(2026, 3, 20, 18, 0, 0)
    with Session(test_engine, expire_on_commit=False) as session:
        pending = ManagedBooking(
            booking_id="b-pending",
            activity_id=31,
            payment_type="membership",
            participation_id="pid-pending",
            class_datetime=now + timedelta(hours=2),
            status=BookingStatus.PENDING,
            reminder_sent=False,
        )
        confirmed = ManagedBooking(
            booking_id="b-confirmed",
            activity_id=32,
            payment_type="membership",
            participation_id="pid-confirmed",
            class_datetime=now + timedelta(hours=2),
            status=BookingStatus.CONFIRMED,
            reminder_sent=False,
        )
        session.add(pending)
        session.add(confirmed)
        session.commit()

        first = booking_cycle.send_due_reminders(session, now, reminder_hours=24)
        assert len(first.prompts) == 2
        callbacks = {
            button.callback_data
            for prompt in first.prompts
            for row in prompt.message.buttons
            for button in row
        }
        assert (
            BookingCallback(
                action=BookingCallbackAction.ACCEPT,
                participation_id="pid-pending",
            ).to_callback_data()
            in callbacks
        )
        assert (
            BookingCallback(
                action=BookingCallbackAction.CANCEL,
                participation_id="pid-confirmed",
            ).to_callback_data()
            in callbacks
        )

        refreshed_pending = session.get(ManagedBooking, pending.id)
        refreshed_confirmed = session.get(ManagedBooking, confirmed.id)
        assert refreshed_pending is not None
        assert refreshed_confirmed is not None
        assert refreshed_pending.reminder_sent is True
        assert refreshed_confirmed.reminder_sent is True

        second = booking_cycle.send_due_reminders(session, now, reminder_hours=24)
        assert second.prompts == []


@pytest.mark.asyncio
async def test_auto_cancel_stale_pending_bookings(configured_jobs, test_engine):
    now = datetime(2026, 3, 20, 18, 0, 0)
    stale = ManagedBooking(
        booking_id="b-stale",
        activity_id=41,
        payment_type="membership",
        participation_id="pid-stale",
        class_datetime=now + timedelta(hours=2),
        status=BookingStatus.PENDING,
    )
    future = ManagedBooking(
        booking_id="b-future",
        activity_id=42,
        payment_type="membership",
        participation_id="pid-future",
        class_datetime=now + timedelta(hours=8),
        status=BookingStatus.PENDING,
    )
    client = FakePureGymClient([])

    with Session(test_engine, expire_on_commit=False) as session:
        session.add(stale)
        session.add(future)
        session.commit()

        result = await booking_cycle.auto_cancel_stale_pending_bookings(
            session,
            cast(PureGymClient, client),
            now,
            auto_cancel_hours=3,
        )

        assert len(result.prompts) == 1
        assert client.unbook_calls == ["pid-stale"]

        refreshed_stale = session.get(ManagedBooking, stale.id)
        refreshed_future = session.get(ManagedBooking, future.id)
        assert refreshed_stale is not None
        assert refreshed_future is not None
        assert refreshed_stale.status == BookingStatus.CANCELLED
        assert refreshed_future.status == BookingStatus.PENDING
