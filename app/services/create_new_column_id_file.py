import asyncio
from sqlalchemy import text
import os
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from dotenv import load_dotenv

load_dotenv()
print(os.getenv('DB_LITE'))

engine = create_async_engine(url=os.getenv('DB_LITE'), echo=True)

session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)



if __name__ == '__main__':
    asyncio.run(create_new_column_id_file())