from datetime import date, datetime, time

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
