from dataclasses import dataclass
from datetime import date, time

from puregym_bot.puregym.schemas import GymClass


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
) -> GymClass:
    return GymClass.model_validate(
        {
            "date": day.isoformat(),
            "startTime": start.isoformat(),
            "endTime": end.isoformat(),
            "title": title,
            "activityId": activity_id,
            "bookingId": booking_id,
            "payment_type": payment_type,
            "participationId": participation_id,
            "instructor": "Coach",
            "location": location,
            "centerName": center_name,
            "centerUrl": "https://example.com/center",
            "duration": 60,
            "activityUrl": "https://example.com/activity",
            "level": {},
            "button": button or {},
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
    def __init__(self, classes):
        self.classes = classes
        self.book_calls: list[str] = []
        self.book_by_ids_calls: list[tuple[str, int, str]] = []
        self.unbook_calls: list[str] = []

    async def get_available_classes(self, **_kwargs):
        return self.classes

    async def book_class(self, gym_class: GymClass):
        self.book_calls.append(gym_class.bookingId)
        return {"status": "success", "participationId": f"p-{gym_class.bookingId}"}

    async def book_by_ids(self, booking_id: str, activity_id: int, payment_type: str):
        self.book_by_ids_calls.append((booking_id, activity_id, payment_type))
        return {"status": "success", "participationId": f"p-{booking_id}"}

    async def unbook_participation(self, participation_id: str):
        self.unbook_calls.append(participation_id)
        return {"status": "success"}
