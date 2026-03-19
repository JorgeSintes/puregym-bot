from datetime import time

import pytest

from puregym_bot.config import GymClassPreferences, TimeSlot, Weekday


def test_time_slots_allow_adjacent_ranges():
    preferences = GymClassPreferences(
        interested_classes=[1],
        interested_centers=[1],
        available_time_slots=[
            TimeSlot(day_of_week=Weekday.MONDAY, start_time=time(17, 0), end_time=time(18, 0)),
            TimeSlot(day_of_week=Weekday.MONDAY, start_time=time(18, 0), end_time=time(20, 0)),
        ],
    )

    assert len(preferences.available_time_slots) == 2


def test_time_slots_reject_overlaps_on_same_day():
    with pytest.raises(ValueError, match="Overlapping time slots are not allowed"):
        GymClassPreferences(
            interested_classes=[1],
            interested_centers=[1],
            available_time_slots=[
                TimeSlot(day_of_week=Weekday.MONDAY, start_time=time(17, 0), end_time=time(19, 0)),
                TimeSlot(day_of_week=Weekday.MONDAY, start_time=time(18, 0), end_time=time(20, 0)),
            ],
        )


def test_time_slots_allow_same_hours_on_different_days():
    preferences = GymClassPreferences(
        interested_classes=[1],
        interested_centers=[1],
        available_time_slots=[
            TimeSlot(day_of_week=Weekday.MONDAY, start_time=time(17, 0), end_time=time(19, 0)),
            TimeSlot(day_of_week=Weekday.TUESDAY, start_time=time(17, 0), end_time=time(19, 0)),
        ],
    )

    assert len(preferences.available_time_slots) == 2
