from datetime import datetime
from enum import Enum

from sqlmodel import Column, DateTime, Field, SQLModel, func


class User(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    telegram_id: int
    name: str
    is_active: bool = False


class BookingStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    ATTENDED = "attended"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class ManagedBooking(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    user_id: int = Field(foreign_key="user.id", index=True)

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
