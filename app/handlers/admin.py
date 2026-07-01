import asyncio
import os
from aiogram import Router, F
from aiogram import types
from aiogram.types import Message, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.fsm.state import StatesGroup, State
from sqlalchemy import select


from app.database.models import Speciality, UserSpeciality, User, Profession, UserProfession
from app.database.orm_query import orm_del_user, orm_get_users, generate_users_csv_dump, generate_professions_csv_dump
from app.filters.is_admin import IsAdmin
from app.keyboards.inline import get_callback_buttons

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



class BroadcastFSM(StatesGroup):
    waiting_for_speciality = State()
    waiting_for_text = State()
    waiting_for_file = State()



@admin_router.message(Command("broadcast"))
async def start_broadcast(message: Message, state: FSMContext, session: AsyncSession):
    # Отримуємо спеціальності
    result = await session.execute(select(Speciality))
    specialities = result.scalars().all()

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text=spec.name, callback_data=f"spec_{spec.id}")]
            for spec in specialities
        ]
    )

    await message.answer("Оберіть спеціальність для розсилки:", reply_markup=keyboard)
    await state.set_state(BroadcastFSM.waiting_for_speciality)


@admin_router.callback_query(BroadcastFSM.waiting_for_speciality, F.data.startswith("spec_"))
async def speciality_chosen(callback: types.CallbackQuery, state: FSMContext):
    spec_id = int(callback.data.split("_")[1])
    await state.update_data(speciality_id=spec_id)

    await callback.message.answer("Введіть текст повідомлення:")
    await state.set_state(BroadcastFSM.waiting_for_text)
    await callback.answer()


@admin_router.message(BroadcastFSM.waiting_for_text)
async def get_broadcast_text(message: types.Message, state: FSMContext):
    await state.update_data(message_text=message.text)
    await message.answer("Надішліть файл, який прикріпити до повідомлення:")
    await state.set_state(BroadcastFSM.waiting_for_file)


@admin_router.message(BroadcastFSM.waiting_for_file, F.document)
async def broadcast_message(message: types.Message, state: FSMContext, session: AsyncSession, bot):
    data = await state.get_data()
    speciality_id = data["speciality_id"]
    text_to_send = data["message_text"]
    document = message.document
    file_id = document.file_id

    # Записуємо file_id у колонку id_file
    stmt = (
        select(Speciality)
        .where(Speciality.id == speciality_id)
    )
    result = await session.execute(stmt)
    speciality = result.scalar_one_or_none()
    if speciality:
        speciality.id_file = file_id
        await session.commit()

    stmt = (
        select(User)
        .join(UserSpeciality)
        .filter(UserSpeciality.speciality_id == speciality_id)
    )
    result = await session.execute(stmt)
    users = result.scalars().all()

    # Формуємо інлайн кнопку
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="Хочу дізнатись", callback_data=f"getfile_{speciality_id}")]
        ]
    )

    count = 0
    for user in users:
        try:
            await bot.send_message(
                chat_id=user.user_id,
                text=text_to_send,
                reply_markup=keyboard
            )
            count += 1
            await asyncio.sleep(0.05)  # антифлуд
        except Exception as e:
            print(f"Не вдалося надіслати {user.user_id}: {e}")

    await message.answer(f"✅ Розсилка завершена. Надіслано {count} користувачам.")
    await state.clear()



# 1. Створюємо окремий клас станів для розсилки по професіях
class BroadcastProfessionFSM(StatesGroup):
    waiting_for_profession = State()
    waiting_for_text = State()
    waiting_for_file = State()


# 2. Початок розсилки за командою /broadcast_profession
@admin_router.message(Command("broadcast_profession"))
async def start_profession_broadcast(message: Message, state: FSMContext, session: AsyncSession):
    # Отримуємо професії
    result = await session.execute(select(Profession))
    professions = result.scalars().all()

    if not professions:
        await message.answer("У базі даних немає жодної професії.")
        return

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text=prof.name, callback_data=f"prof_{prof.id}")]
            for prof in professions
        ]
    )

    await message.answer("Оберіть професію для розсилки:", reply_markup=keyboard)
    await state.set_state(BroadcastProfessionFSM.waiting_for_profession)


# 3. Обробка вибору професії
@admin_router.callback_query(BroadcastProfessionFSM.waiting_for_profession, F.data.startswith("prof_"))
async def profession_chosen(callback: types.CallbackQuery, state: FSMContext):
    prof_id = int(callback.data.split("_")[1])
    await state.update_data(profession_id=prof_id)

    await callback.message.answer("Введіть текст повідомлення:")
    await state.set_state(BroadcastProfessionFSM.waiting_for_text)
    await callback.answer()


# 4. Обробка тексту повідомлення
@admin_router.message(BroadcastProfessionFSM.waiting_for_text)
async def get_profession_broadcast_text(message: types.Message, state: FSMContext):
    await state.update_data(message_text=message.text)
    await message.answer("Надішліть файл, який прикріпити до повідомлення:")
    await state.set_state(BroadcastProfessionFSM.waiting_for_file)


# 5. Отримання файлу, збереження ID у БД та розсилка
@admin_router.message(BroadcastProfessionFSM.waiting_for_file, F.document)
async def broadcast_profession_message(message: types.Message, state: FSMContext, session: AsyncSession, bot):
    data = await state.get_data()
    profession_id = data["profession_id"]
    text_to_send = data["message_text"]
    document = message.document
    file_id = document.file_id

    # Записуємо file_id у колонку id_file таблиці Profession
    stmt = (
        select(Profession)
        .where(Profession.id == profession_id)
    )
    result = await session.execute(stmt)
    profession = result.scalar_one_or_none()

    if profession:
        profession.id_file = file_id
        await session.commit()

    # Шукаємо всіх користувачів, які підписані на цю професію
    stmt = (
        select(User)
        .join(UserProfession)
        .filter(UserProfession.profession_id == profession_id)
    )
    result = await session.execute(stmt)
    users = result.scalars().all()

    # Формуємо інлайн кнопку. Зверніть увагу: callback_data змінено на getfile_prof_,
    # щоб відрізняти запити на файли професій від спеціальностей.
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="Хочу дізнатись", callback_data=f"prof_getfile_{profession_id}")]
        ]
    )

    count = 0
    for user in users:
        try:
            await bot.send_message(
                chat_id=user.user_id,
                text=text_to_send,
                reply_markup=keyboard
            )
            count += 1
            await asyncio.sleep(0.05)  # антифлуд
        except Exception as e:
            print(f"Не вдалося надіслати {user.user_id}: {e}")

    await message.answer(f"✅ Розсилка завершена. Надіслано {count} користувачам, які цікавляться цією професією.")
    await state.clear()


@admin_router.message(Command("dump"))
async def send_db_dump(message: Message, session: AsyncSession):
    await message.answer("⏳ Формую дамп бази даних. Зачекайте...")

    file_path = None

    try:
        # 2. Викликаємо нашу функцію генерації
        file_path = await generate_users_csv_dump(session)

        # 3. Відправляємо файл у Telegram
        document = FSInputFile(file_path)
        await message.answer_document(
            document=document,
            caption="✅ Дамп бази даних успішно сформовано!"
        )

    except Exception as e:
        await message.answer(f"❌ Виникла помилка при створенні дампу: {e}")

    finally:
        # 4. Прибираємо за собою (видаляємо файл з сервера після відправки)
        if file_path is not None and os.path.exists(file_path):
            os.remove(file_path)


@admin_router.message(Command("dump_profession"))
async def send_profession_db_dump(message: Message, session: AsyncSession):
    await message.answer("⏳ Формую дамп бази даних професій. Зачекайте...")

    file_path = None

    try:
        # Викликаємо функцію генерації дампу для професій
        file_path = await generate_professions_csv_dump(session)

        # Відправляємо файл у Telegram
        document = FSInputFile(file_path, filename="professions_dump.csv")
        await message.answer_document(
            document=document,
            caption="✅ Дамп бази даних (професії) успішно сформовано!"
        )

    except Exception as e:
        await message.answer(f"❌ Виникла помилка при створенні дампу професій: {e}")

    finally:
        # Прибираємо за собою (видаляємо тимчасовий файл з сервера)
        if file_path is not None and os.path.exists(file_path):
            os.remove(file_path)