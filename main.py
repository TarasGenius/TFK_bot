import asyncio
import logging
import os
from aiogram import Bot, Dispatcher

from dotenv import load_dotenv, find_dotenv

from app.database.engine import create_db, session_maker, add_new_speciality, add_new_profession, create_new_column_id_file

load_dotenv(find_dotenv())

from app.handlers.user import user_router
from app.handlers.admin import admin_router
from app.handlers.ai import ai_router
from app.handlers.user_profession import user_profession
from app.services.vector_db import load_knowledge_base

from app.middlewares.db import DataBaseSession


bot = Bot(token=os.getenv('TOKEN'))
bot.my_admins_list = list(map(int, str(os.getenv('ADMINS')).split(',')))

dp = Dispatcher()
dp.include_router(admin_router)
dp.include_router(user_router)
dp.include_router(user_profession)
dp.include_router(ai_router)

async def on_startup(bot):

    await create_db()


async def on_shutdown(bot):
    print('Бот ліг')

async def main():
    load_knowledge_base()
    await add_new_speciality()
    await add_new_profession()
    # await create_new_column_id_file()
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    dp.update.middleware(DataBaseSession(session_pool=session_maker))

    await bot.delete_webhook(drop_pending_updates=True)

    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('pressed exit')