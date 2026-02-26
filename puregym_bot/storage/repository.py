from sqlmodel import Session, col, select

from puregym_bot.storage.models import BookingStatus, ManagedBooking, User


def get_all_users(session: Session) -> list[User]:
    return list(session.exec(select(User)).all())


def get_active_users(session: Session) -> list[User]:
    return list(session.exec(select(User).where(col(User.is_active).is_(True))).all())


def get_user_by_telegram_id(session: Session, telegram_id: int) -> User | None:
    statement = select(User).where(User.telegram_id == telegram_id)
    return session.exec(statement).first()


def set_user_active(session: Session, user: User, is_active: bool) -> None:
    user.is_active = is_active
    session.add(user)


def get_booking_by_participation_id(session: Session, participation_id: str) -> ManagedBooking | None:
    statement = select(ManagedBooking).where(ManagedBooking.participation_id == participation_id)
    return session.exec(statement).first()


def get_booking_by_booking_id(session: Session, booking_id: str) -> ManagedBooking | None:
    statement = select(ManagedBooking).where(ManagedBooking.booking_id == booking_id)
    return session.exec(statement).first()


def get_active_bookings(session: Session, user_id: int) -> list[ManagedBooking]:
    statement = select(ManagedBooking).where(
        ManagedBooking.user_id == user_id,
        col(ManagedBooking.status).in_([BookingStatus.PENDING.value, BookingStatus.CONFIRMED.value]),
    )
    return list(session.exec(statement).all())


def get_pending_bookings(session: Session, user_id: int) -> list[ManagedBooking]:
    statement = select(ManagedBooking).where(
        ManagedBooking.user_id == user_id,
        ManagedBooking.status == BookingStatus.PENDING,
    )
    return list(session.exec(statement).all())


def add_managed_booking(session: Session, booking: ManagedBooking) -> None:
    session.add(booking)


def set_booking_status(session: Session, booking: ManagedBooking, status: BookingStatus) -> None:
    booking.status = status
    session.add(booking)


def set_reminder_sent(session: Session, booking: ManagedBooking) -> None:
    booking.reminder_sent = True
    session.add(booking)


def set_message_id(session: Session, booking: ManagedBooking, message_id: int) -> None:
    booking.telegram_message_id = message_id
    session.add(booking)
