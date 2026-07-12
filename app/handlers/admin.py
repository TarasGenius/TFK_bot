import asyncio
import os
import tempfile
import pandas as pd
from aiogram import Router, F, types, Bot
from aiogram.types import Message, FSInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.fsm.state import StatesGroup, State
from sqlalchemy import select


from app.database.models import Speciality, UserSpeciality, User, Profession, UserProfession
from app.database.orm_query import orm_del_user, orm_get_users, generate_users_csv_dump, generate_professions_csv_dump
from app.filters.is_admin import IsAdmin
from app.services.generate_doc import generate_merged_document

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



class DocGenState(StatesGroup):
    waiting_for_template = State()
    waiting_for_csv = State()
    waiting_for_declension = State()
    processing = State()


@admin_router.message(Command("generate"))
async def start_generation(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Відправте файл шаблону у форматі **.docx**.")
    await state.set_state(DocGenState.waiting_for_template)


@admin_router.message(DocGenState.waiting_for_template, F.document)
async def process_template(message: Message, bot: Bot, state: FSMContext):
    if not message.document.file_name.endswith('.docx'):
        return await message.answer("Це не .docx файл. Відправте правильний шаблон.")

    template_path = tempfile.mktemp(suffix=".docx")
    await bot.download(message.document, destination=template_path)

    await state.update_data(template_path=template_path)
    await message.answer("Чудово! Тепер відправте **.csv** файл із даними.")
    await state.set_state(DocGenState.waiting_for_csv)


@admin_router.message(DocGenState.waiting_for_csv, F.document)
async def process_csv(message: Message, bot: Bot, state: FSMContext):
    if not message.document.file_name.endswith('.csv'):
        return await message.answer("Це не .csv файл. Відправте правильний файл даних.")

    csv_path = tempfile.mktemp(suffix=".csv")
    await bot.download(message.document, destination=csv_path)

    df = pd.read_csv(csv_path, nrows=0)
    columns = list(df.columns)

    await state.update_data(
        csv_path=csv_path,
        columns=columns,
        current_col_index=0,
        declension_rules={}
    )

    await ask_next_column(message, state)


async def ask_next_column(message_or_call, state: FSMContext):
    data = await state.get_data()
    columns = data['columns']
    current_col_index = data['current_col_index']

    if current_col_index < len(columns):
        col_name = columns[current_col_index]

        # Клавіатура з вибором відмінка
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Не відмінювати", callback_data="case_none")],
            [InlineKeyboardButton(text="Кого? Чого? (Родовий)", callback_data="case_gent")],
            [InlineKeyboardButton(text="Кому? Чому? (Давальний)", callback_data="case_datv")],
            [InlineKeyboardButton(text="Ким? Чим? (Орудний)", callback_data="case_ablt")]
        ])

        text = f"Оберіть відмінок для стовпчика: **{col_name}**\n\n*(Якщо колонка містить слово 'name', 'піб' або 'ім'я', буде застосовано розумне відмінювання для ПІБ)*"

        if isinstance(message_or_call, Message):
            await message_or_call.answer(text, reply_markup=kb)
        else:
            await message_or_call.message.edit_text(text, reply_markup=kb)

        await state.set_state(DocGenState.waiting_for_declension)
    else:
        await start_document_generation(message_or_call, state)


@admin_router.callback_query(DocGenState.waiting_for_declension, F.data.startswith("case_"))
async def process_declension_answer(call: CallbackQuery, state: FSMContext):
    # Отримуємо відмінок (наприклад, 'gent', 'datv' або 'none')
    selected_case = call.data.split("_")[1]

    data = await state.get_data()
    columns = data['columns']
    current_col_index = data['current_col_index']
    declension_rules = data['declension_rules']

    col_name = columns[current_col_index]
    declension_rules[col_name] = selected_case

    await state.update_data(
        current_col_index=current_col_index + 1,
        declension_rules=declension_rules
    )

    await ask_next_column(call, state)


async def start_document_generation(call: CallbackQuery, state: FSMContext):
    await state.set_state(DocGenState.processing)
    await call.message.edit_text("⏳ Генерую документи... Зачекайте хвилинку!")

    data = await state.get_data()

    try:
        final_doc_path = await asyncio.to_thread(
            generate_merged_document,
            data['template_path'],
            data['csv_path'],
            data['declension_rules']
        )

        result_file = FSInputFile(final_doc_path, filename="Згенеровані_документи.docx")
        await call.message.answer_document(result_file, caption="✅ Готово! Ваші документи згенеровано.")

        os.remove(final_doc_path)
        os.remove(data['template_path'])
        os.remove(data['csv_path'])

    except Exception as e:
        await call.message.answer(f"❌ Сталася помилка під час генерації: {e}")
    finally:
        await state.clear()