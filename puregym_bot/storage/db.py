from contextlib import contextmanager
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from puregym_bot.storage.models import BotState

DATABASE_DIR = Path("data")
DATABASE_PATH = DATABASE_DIR / "puregym_bot.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},  # needed for async telegram handlers
)


def ensure_database_dir() -> None:
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)


def init_db() -> None:
    ensure_database_dir()
    # Create DB file + tables if not exists
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        if session.get(BotState, 1) is None:
            session.add(BotState(id=1, is_active=True))
            session.commit()


@contextmanager
def get_db_session():
    ensure_database_dir()
    with Session(engine, expire_on_commit=False) as session:
        yield session


if __name__ == "__main__":
    init_db()
