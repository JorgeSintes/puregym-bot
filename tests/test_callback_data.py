import pytest

from puregym_bot.bot.callback_data import (
    BookingCallback,
    BookingCallbackAction,
    ChoicePickCallback,
    parse_callback_data,
)


def test_parse_callback_data_round_trips_booking_callbacks():
    accept = BookingCallback(
        action=BookingCallbackAction.ACCEPT,
        participation_id="pid-123",
    )
    cancel = BookingCallback(
        action=BookingCallbackAction.CANCEL,
        participation_id="pid-456",
    )
    revert_pending = BookingCallback(
        action=BookingCallbackAction.REVERT_PENDING,
        participation_id="pid-789",
    )

    assert parse_callback_data(accept.to_callback_data()) == accept
    assert parse_callback_data(cancel.to_callback_data()) == cancel
    assert parse_callback_data(revert_pending.to_callback_data()) == revert_pending


def test_parse_callback_data_round_trips_choice_pick_callback():
    callback = ChoicePickCallback(choice_id=12, option_index=3)

    assert parse_callback_data(callback.to_callback_data()) == callback


def test_specific_callback_parsers_raise_for_malformed_payloads():
    with pytest.raises(ValueError):
        BookingCallback.from_callback_data("booking:maybe:pid-123")

    with pytest.raises(ValueError):
        ChoicePickCallback.from_callback_data("choice:pick:abc:1")


def test_parse_callback_data_rejects_malformed_payloads():
    assert parse_callback_data("") is None
    assert parse_callback_data("accept:pid-123") is None
    assert parse_callback_data("booking:maybe:pid-123") is None
    assert parse_callback_data("choice:pick:abc:1") is None
    assert parse_callback_data("choice:pick:12:-1") is None
