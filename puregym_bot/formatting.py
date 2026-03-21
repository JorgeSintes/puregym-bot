from datetime import date, datetime, time, timedelta
from typing import Protocol


class BookingDisplay(Protocol):
    date: str
    startTime: str
    title: str
    location: str
    waitlist_position: int | None


WEEKDAY_ABBREVIATIONS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def format_telegram_date(value: str | date) -> str:
    parsed = value if isinstance(value, date) else date.fromisoformat(value)
    return f"{WEEKDAY_ABBREVIATIONS[parsed.weekday()]} {parsed.strftime('%d/%m')}"


def format_telegram_time(value: str | time) -> str:
    parsed = value if isinstance(value, time) else time.fromisoformat(value)
    return parsed.strftime("%H:%M")


def format_telegram_datetime(value: str | datetime) -> str:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value)
    return f"{WEEKDAY_ABBREVIATIONS[parsed.weekday()]} {parsed.strftime('%d/%m %H:%M')}"


def format_telegram_class_time(class_date: str, start_time: str) -> str:
    return f"{format_telegram_date(class_date)} {format_telegram_time(start_time)}"


def format_telegram_class_summary(class_date: str, start_time: str, title: str, location: str) -> str:
    return f"{format_telegram_class_time(class_date, start_time)}  {title} @ {location}"


def format_telegram_booking(booking: BookingDisplay) -> str:
    class_date = datetime.fromisoformat(booking.date).date()
    start_time = time.fromisoformat(booking.startTime)
    class_dt = datetime.combine(class_date, start_time)
    cancel_deadline = class_dt - timedelta(hours=3)
    message = (
        f"{format_telegram_class_summary(booking.date, booking.startTime, booking.title, booking.location)} "
        f"| cancel by {format_telegram_datetime(cancel_deadline)}"
    )
    if booking.waitlist_position is not None:
        return f"{message} | waitlist #{booking.waitlist_position}"
    return message
