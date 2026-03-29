from dataclasses import dataclass
from enum import StrEnum


class BookingCallbackAction(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"
    CANCEL = "cancel"
    REVERT_PENDING = "revert_pending"


@dataclass(frozen=True)
class BookingCallback:
    action: BookingCallbackAction
    participation_id: str

    def to_callback_data(self) -> str:
        return f"booking:{self.action}:{self.participation_id}"

    @classmethod
    def from_callback_data(cls, data: str) -> "BookingCallback":
        parts = data.split(":")
        if len(parts) != 3 or parts[0] != "booking" or not parts[2]:
            raise ValueError("Invalid booking callback data")

        try:
            action = BookingCallbackAction(parts[1])
        except ValueError:
            raise ValueError("Invalid booking callback action") from None

        return cls(action=action, participation_id=parts[2])


@dataclass(frozen=True)
class ChoicePickCallback:
    choice_id: int
    option_index: int

    def to_callback_data(self) -> str:
        return f"choice:pick:{self.choice_id}:{self.option_index}"

    @classmethod
    def from_callback_data(cls, data: str) -> "ChoicePickCallback":
        parts = data.split(":")
        if len(parts) != 4 or parts[0] != "choice" or parts[1] != "pick":
            raise ValueError("Invalid choice callback data")

        try:
            choice_id = int(parts[2])
            option_index = int(parts[3])
        except ValueError:
            raise ValueError("Choice callback IDs must be integers") from None

        if choice_id <= 0 or option_index < 0:
            raise ValueError("Choice callback IDs are out of range")

        return cls(choice_id=choice_id, option_index=option_index)


ParsedCallback = BookingCallback | ChoicePickCallback


def parse_callback_data(data: str) -> ParsedCallback | None:
    for parser in (BookingCallback.from_callback_data, ChoicePickCallback.from_callback_data):
        try:
            return parser(data)
        except ValueError:
            continue
    return None
