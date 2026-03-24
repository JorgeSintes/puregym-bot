from datetime import date, datetime, time, timedelta

WEEKDAY_ABBREVIATIONS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _parse_date(value: str | date) -> date:
    return value if isinstance(value, date) else date.fromisoformat(value)


def _parse_time(value: str | time) -> time:
    return value if isinstance(value, time) else time.fromisoformat(value)


def _parse_datetime(value: str | datetime) -> datetime:
    return value if isinstance(value, datetime) else datetime.fromisoformat(value)


def _format_telegram_when(class_date: str | date, start_time: str | time | None = None) -> str:
    parsed_date = _parse_date(class_date)
    formatted = f"{WEEKDAY_ABBREVIATIONS[parsed_date.weekday()]} {parsed_date.strftime('%d/%m')}"
    if start_time is None:
        return formatted
    return f"{formatted} {_parse_time(start_time).strftime('%H:%M')}"


def format_telegram_date(value: str | date) -> str:
    return _format_telegram_when(value)


def format_telegram_time(value: str | time) -> str:
    return _parse_time(value).strftime("%H:%M")


def format_telegram_datetime(value: str | datetime) -> str:
    parsed = _parse_datetime(value)
    return _format_telegram_when(parsed.date(), parsed.time())


def format_telegram_class_summary(class_date: str, start_time: str, title: str, location: str) -> str:
    return f"{_format_telegram_when(class_date, start_time)}  {title} @ {location}"


def format_telegram_booking(
    *,
    title: str,
    location: str,
    class_date: str | date | None = None,
    start_time: str | time | None = None,
    class_datetime: str | datetime | None = None,
    waitlist_position: int | None = None,
    include_cancel_deadline: bool = True,
) -> str:
    if class_datetime is None:
        if class_date is None or start_time is None:
            raise ValueError("Either class_datetime or both class_date and start_time must be provided")
        class_dt = datetime.combine(_parse_date(class_date), _parse_time(start_time))
    else:
        class_dt = _parse_datetime(class_datetime)

    message = f"{format_telegram_class_summary(class_dt.date().isoformat(), class_dt.time().isoformat(), title, location)}"
    if waitlist_position is not None:
        message = f"{message} | waitlist #{waitlist_position}"
    if include_cancel_deadline:
        cancel_deadline = class_dt - timedelta(hours=3)
        message = f"{message} | cancel by {format_telegram_datetime(cancel_deadline)}"
    return message
