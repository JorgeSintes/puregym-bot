from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from puregym_mcp.puregym.models import GymClass


def make_gym_class(
    *,
    booking_id: str,
    activity_id: int,
    day: date,
    start: time,
    end: time,
    participation_id: str | None,
    title: str = "Body Pump",
    location: str = "Main Hall",
    center_name: str = "Center 1",
    payment_type: str = "membership",
    button: dict | None = None,
    waitlist_position: int | None = None,
    waitlist_size: int | None = None,
) -> GymClass:
    return GymClass.model_validate(
        {
            "date": day.isoformat(),
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "title": title,
            "activity_id": activity_id,
            "booking_id": booking_id,
            "payment_type": payment_type,
            "participation_id": participation_id,
            "instructor": "Coach",
            "location": location,
            "center_name": center_name,
            "center_url": "https://example.com/center",
            "duration": 60,
            "activity_url": "https://example.com/activity",
            "level": None,
            "button": button or {},
            "waitlist_position": waitlist_position,
            "waitlist_size": waitlist_size,
        }
    )


def make_dashboard_booking(
    *,
    day: date,
    start: time,
    participation_id: str,
    title: str = "Body Pump",
    location: str = "Main Hall",
    center_name: str = "Center 1",
    button_description: str | None = None,
) -> GymClass:
    return GymClass.model_validate(
        {
            "date": day.isoformat(),
            "start_time": start.isoformat(),
            "end_time": (datetime.combine(day, start) + timedelta(minutes=60)).time().isoformat(),
            "title": title,
            "activity_id": 1,
            "booking_id": f"booking-{participation_id}",
            "payment_type": "membership",
            "participation_id": participation_id,
            "instructor": "Coach",
            "location": location,
            "center_name": center_name,
            "center_url": "https://example.com/center",
            "duration": 60,
            "activity_url": "https://example.com/activity",
            "level": None,
        }
    )


@dataclass
class FakeSentMessage:
    message_id: int


class FakeBot:
    def __init__(self):
        self.calls: list[dict] = []
        self._message_id = 100

    async def send_message(self, *, chat_id: int, text: str, reply_markup=None):
        self._message_id += 1
        self.calls.append(
            {
                "chat_id": chat_id,
                "text": text,
                "reply_markup": reply_markup,
                "message_id": self._message_id,
            }
        )
        return FakeSentMessage(message_id=self._message_id)


class FakeContext:
    def __init__(self, client):
        self.bot = FakeBot()
        self.bot_data = {"puregym_client": client}


class FakePureGymClient:
    def __init__(self, classes, bookings=None):
        self.classes = classes
        self.bookings = bookings if bookings is not None else classes
        self.book_calls: list[str] = []
        self.book_by_ids_calls: list[tuple[str, int, str]] = []
        self.unbook_calls: list[str] = []

    async def get_available_classes(self, **_kwargs):
        return self.classes

    async def get_my_bookings(self):
        return self.bookings

    async def book_class(self, gym_class: GymClass):
        self.book_calls.append(gym_class.booking_id)
        return {"status": "success", "participation_id": f"p-{gym_class.booking_id}"}

    async def book_by_ids(self, booking_id: str, activity_id: int, payment_type: str):
        self.book_by_ids_calls.append((booking_id, activity_id, payment_type))
        return {"status": "success", "participation_id": f"p-{booking_id}"}

    async def unbook_participation(self, participation_id: str):
        self.unbook_calls.append(participation_id)
        return {"status": "success"}
