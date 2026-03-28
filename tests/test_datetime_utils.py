from datetime import datetime

from puregym_bot.bot.booking_cycle import class_datetime
from puregym_bot.datetime_utils import APP_TIMEZONE, combine_copenhagen, copenhagen_now
from puregym_mcp.puregym.models import GymClass


def test_copenhagen_now_returns_naive_local_datetime() -> None:
    now = copenhagen_now()

    assert now.tzinfo is None


def test_combine_copenhagen_uses_local_wall_time() -> None:
    class_dt = combine_copenhagen("2026-03-23", "18:30:00")

    assert class_dt == datetime(2026, 3, 23, 18, 30)
    assert class_dt.tzinfo is None


def test_class_datetime_keeps_puregym_local_time() -> None:
    gym_class = GymClass.model_validate(
        {
            "date": "2026-03-23",
            "start_time": "18:30:00",
            "end_time": "19:30:00",
            "title": "Yoga",
            "activity_id": 1,
            "booking_id": "booking-1",
            "payment_type": "free",
            "participation_id": None,
            "instructor": "Instructor",
            "location": "Studio",
            "center_name": "Center",
            "center_url": "/center",
            "duration": 60,
            "activity_url": "/activity",
            "level": None,
            "button": {},
        }
    )

    assert class_datetime(gym_class) == datetime(2026, 3, 23, 18, 30)


def test_app_timezone_is_copenhagen() -> None:
    assert APP_TIMEZONE.key == "Europe/Copenhagen"
