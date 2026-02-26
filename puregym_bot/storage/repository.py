from sqlmodel import Session, select

from puregym_bot.storage.models import User


def get_all_users(session: Session) -> list[User]:
    return list(session.exec(select(User)).all())


def get_user_by_telegram_id(session: Session, telegram_id: int) -> User | None:
    statement = select(User).where(User.telegram_id == telegram_id)
    return session.exec(statement).first()
