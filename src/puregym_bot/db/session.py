from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from puregym_bot.db.schemas import *


def get_engine():
    return create_async_engine("sqlite+aiosqlite:///puregym_bot.db", echo=False)


def get_session():
    engine = get_engine()
    return AsyncSession(engine)


async def init_db():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
