from datetime import datetime
from enum import Enum

from sqlmodel import Column, DateTime, Field, SQLModel, func


class BotState(SQLModel, table=True):
    id: int = Field(primary_key=True)
    is_active: bool = False


class BookingStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    ATTENDED = "attended"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class ManagedBooking(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    # PureGym identifiers
    booking_id: str = Field(index=True)
    activity_id: int
    payment_type: str
    participation_id: str | None = None
    telegram_message_id: int | None = None

    # Class timing (so we can reason about reminders)
    class_datetime: datetime = Field(index=True)

    # Bot state
    status: BookingStatus = Field(default=BookingStatus.PENDING)
    reminder_sent: bool = False

    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )


class ChoiceStatus(str, Enum):
    PENDING = "pending"
    HANDLED = "handled"
    EXPIRED = "expired"


class BookingChoice(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    slot_date: str = Field(index=True)
    slot_start: str
    slot_end: str

    options_json: str
    message_id: int | None = None

    status: ChoiceStatus = Field(default=ChoiceStatus.PENDING)
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
