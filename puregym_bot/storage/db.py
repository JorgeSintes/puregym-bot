from contextlib import contextmanager
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine, select

from puregym_bot.config import UserConfig
from puregym_bot.storage.models import User

DATABASE_PATH = Path("puregym_bot.db")
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},  # needed for async telegram handlers
)


def init_db(users: list[UserConfig]) -> None:
    # Create DB file + tables if not exists
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        for user_config in users:
            statement = select(User).where(User.telegram_id == user_config.telegram_id)
            user = session.exec(statement).first()

            if user is None:
                user = User(
                    name=user_config.name,
                    telegram_id=user_config.telegram_id,
                )
                session.add(user)
                session.commit()


@contextmanager
def get_db_session():
    with Session(engine) as session:
        yield session
