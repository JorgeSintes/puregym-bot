import re
from datetime import datetime, timedelta, time

from pydantic import BaseModel

from puregym_bot.formatting import format_telegram_class_time, format_telegram_datetime

WAITLIST_POSITION_PATTERN = re.compile(r"nr\.\s*(\d+)\s+pa\s+ventelisten", re.IGNORECASE)
WAITLIST_SIZE_PATTERN = re.compile(r"Venteliste\s*\((\d+)\)", re.IGNORECASE)


class GymClassType(BaseModel):
    label: str
    value: int
    type: str


class GymClassTypesGroup(BaseModel):
    title: str
    options: list[GymClassType]

    def format(self) -> str:
        lines = [f"<b>{self.title}</b>"]

        for option in self.options:
            lines.append(f"• {option.label} → <code>{option.value}</code>")

        return "\n".join(lines)


class Center(BaseModel):
    label: str
    value: int
    type: str


class CenterGroup(BaseModel):
    label: str
    weight: int
    options: list[Center]

    def format(self) -> str:
        lines = [f"<b>{self.label}</b>"]

        for option in self.options:
            lines.append(f"• {option.label} → <code>{option.value}</code>")

        return "\n".join(lines)


class GymClass(BaseModel):
    date: str
    startTime: str
    endTime: str
    title: str
    activityId: int
    bookingId: str
    payment_type: str
    participationId: str | None
    instructor: str
    location: str
    centerName: str
    centerUrl: str
    duration: int
    activityUrl: str
    level: dict
    button: dict

    @property
    def button_description(self) -> str | None:
        description = self.button.get("description")
        if isinstance(description, str):
            return description
        return None

    @property
    def waitlist_position(self) -> int | None:
        description = self.button_description
        if description is None:
            return None

        normalized = description.lower().replace("å", "a")
        match = WAITLIST_POSITION_PATTERN.search(normalized)
        if match is None:
            return None
        return int(match.group(1))

    @property
    def waitlist_size(self) -> int | None:
        description = self.button_description
        if description is None:
            return None

        match = WAITLIST_SIZE_PATTERN.search(description)
        if match is None:
            return None
        return int(match.group(1))

    @property
    def is_waitlisted(self) -> bool:
        return self.waitlist_position is not None or self.waitlist_size is not None

    def format(self) -> str:
        class_date = datetime.fromisoformat(self.date).date()
        start_time = time.fromisoformat(self.startTime)
        class_dt = datetime.combine(class_date, start_time)
        cancel_deadline = class_dt - timedelta(hours=3)
        message = (
            f"{self.title} on {format_telegram_class_time(self.date, self.startTime)} "
            f"({self.location}) | cancel by {format_telegram_datetime(cancel_deadline)}"
        )
        if self.waitlist_position is not None:
            return f"{message} | waitlist #{self.waitlist_position}"
        return message
