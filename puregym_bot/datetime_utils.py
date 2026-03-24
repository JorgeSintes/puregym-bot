from datetime import date, datetime, time
from zoneinfo import ZoneInfo


APP_TIMEZONE = ZoneInfo("Europe/Copenhagen")


def _parse_date(value: str | date) -> date:
    return value if isinstance(value, date) else date.fromisoformat(value)


def _parse_time(value: str | time) -> time:
    return value if isinstance(value, time) else time.fromisoformat(value)


def copenhagen_now() -> datetime:
    return datetime.now(APP_TIMEZONE).replace(tzinfo=None)


def combine_copenhagen(class_date: str | date, class_time: str | time) -> datetime:
    return datetime.combine(_parse_date(class_date), _parse_time(class_time))
