from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.orm_query import orm_del_user, orm_get_users
from app.filters.is_admin import IsAdmin

admin_router = Router()
admin_router.message.filter(IsAdmin())

@admin_router.message(F.text.startswith("видали"))
async def admin_delete_user_by_id(message: Message, session: AsyncSession):
    text = message.text.strip()
    try:
        id = int(text.split()[1])
    except (IndexError, ValueError):
        await message.answer("❌ Вкажіть ID після команди. Приклад: 'видали 5'")
        return

    result = await orm_del_user(session, id)

    if result:
        await message.answer(f"✅ Користувач з ID {id} успішно видалений.")
    else:
        await message.answer(f"❌ Користувача з ID {id} не знайдено.")


@admin_router.message(Command('get'))
async def admin_get_users(message: Message, session: AsyncSession):
    users = await orm_get_users(session)

    if not users:
        await message.answer("У базі немає користувачів.")
        return

    text = "👥 Список користувачів:\n\n"
    for user in users:
        text += f"ID: {user.id} | {user.full_name} | @{user.reg_phone}\n"

    # У разі якщо список занадто довгий
    if len(text) > 4000:
        for chunk in [text[i:i + 4000] for i in range(0, len(text), 4000)]:
            await message.answer(chunk)
    else:
        await message.answer(text)

