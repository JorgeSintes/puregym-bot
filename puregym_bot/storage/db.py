from contextlib import contextmanager
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from puregym_bot.storage.models import BotState

DATABASE_PATH = Path("puregym_bot.db")
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},  # needed for async telegram handlers
)


def init_db() -> None:
    # Create DB file + tables if not exists
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        if session.get(BotState, 1) is None:
            session.add(BotState(id=1, is_active=True))
            session.commit()


@contextmanager
def get_db_session():
    with Session(engine, expire_on_commit=False) as session:
        yield session


if __name__ == "__main__":
    init_db()
