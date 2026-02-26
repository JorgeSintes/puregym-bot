from sqlmodel import Session, select

from puregym_bot.storage.models import User


def get_all_users(session: Session) -> list[User]:
    return list(session.exec(select(User)).all())


def get_user_by_telegram_id(session: Session, telegram_id: int) -> User | None:
    statement = select(User).where(User.telegram_id == telegram_id)
    return session.exec(statement).first()


def set_user_active(session: Session, user: User, is_active: bool) -> None:
    user.is_active = is_active
    session.add(user)
    session.commit()
