from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = "postgresql+asyncpg://drug_user:drug_pass@localhost:5432/drug_db"

engine = create_async_engine(DATABASE_URL, echo=False)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

from app.orm_models import Base


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session