from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.filters.callback_data import CallbackData
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command
from aiogram import F, Router
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select


from app.database.models import User, Profession, Answer
from app.database.orm_query import orm_get_professions, orm_set_user_professions

user_profession = Router()
# 1. Стан для вибору професій
class AddProfession(StatesGroup):
    choosing_profession = State()


# 2. Фабрика Callback'ів для професій
class ProfessionCallback(CallbackData, prefix="prof"):
    action: str
    profession_id: int | None = None


# 3. Функція створення клавіатури для професій
async def create_professions_keyboard(
        professions: list,
        selected: list[int]
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for prof in professions:
        text = f"✅ {prof.name}" if prof.id in selected else prof.name
        builder.button(
            text=text,
            callback_data=ProfessionCallback(action="select", profession_id=prof.id).pack()
        )
    builder.adjust(1)
    builder.row(
        InlineKeyboardButton(
            text="Підтвердити вибір",
            callback_data=ProfessionCallback(action="confirm").pack()
        )
    )
    return builder.as_markup()


# 4. Хендлер команди /profession (Початок вибору професій)
@user_profession.message(Command('profession'))
async def add_profession_cmd(message: Message, state: FSMContext, session: AsyncSession):
    # 1. ПЕРЕВІРКА РЕЄСТРАЦІЇ
    # Шукаємо користувача в базі за його Telegram ID
    user_query = select(User).where(User.user_id == message.from_user.id)
    user_result = await session.execute(user_query)
    registered_user = user_result.scalar_one_or_none()

    # Якщо користувача немає, просимо зареєструватися і зупиняємо функцію
    if not registered_user:
        await message.answer("⚠️ Спочатку потрібно зареєструватися!\n\nВикличте команду /register, щоб заповнити дані, а потім повертайтеся до вибору професій.")
        return

    # 2. ЯКЩО ЗАРЕЄСТРОВАНИЙ - ПРОДОВЖУЄМО ЛОГІКУ
    professions = await orm_get_professions(session)
    if not professions:
        await message.answer("На жаль, наразі немає доступних професій для вибору.")
        return

    # Переходимо на етап вибору професій
    await state.set_state(AddProfession.choosing_profession)
    await state.update_data(selected_ids=[])  # Пустий список вибору

    keyboard = await create_professions_keyboard(professions, [])
    await message.answer("Оберіть одну або декілька професій (Кваліфікований робітник):", reply_markup=keyboard)

# 5. Обробка натискання на конкретну професію (вибір/скасування)
@user_profession.callback_query(AddProfession.choosing_profession, ProfessionCallback.filter(F.action == "select"))
async def process_profession_select(callback: CallbackQuery, callback_data: ProfessionCallback, state: FSMContext,
                                    session: AsyncSession):
    data = await state.get_data()
    selected_ids = data.get("selected_ids", [])
    prof_id = callback_data.profession_id

    if prof_id in selected_ids:
        selected_ids.remove(prof_id)
    else:
        selected_ids.append(prof_id)

    await state.update_data(selected_ids=selected_ids)

    professions = await orm_get_professions(session)
    keyboard = await create_professions_keyboard(professions, selected_ids)

    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()


# 6. Підтвердження вибору та збереження в БД
@user_profession.callback_query(AddProfession.choosing_profession, ProfessionCallback.filter(F.action == "confirm"))
async def process_profession_confirm(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    selected_ids = data.get("selected_ids", [])

    if not selected_ids:
        await callback.answer("Ви не обрали жодної професії.", show_alert=True)
        return

    try:
        # Зберігаємо обрані професії для користувача
        await orm_set_user_professions(session, user_id=callback.from_user.id, profession_ids=selected_ids)
        await callback.message.edit_text("✅ Ваші професії успішно збережено!")
    except Exception as e:
        await callback.message.edit_text("❌ Виникла помилка під час збереження професій.")
        print(f"Помилка: {e}")
    finally:
        await state.clear()

    await callback.answer()


@user_profession.callback_query(F.data.startswith("prof_getfile_"))
async def send_profession_requested_file(callback: CallbackQuery, session: AsyncSession, bot):
    try:
        # Розбиваємо "getfile_prof_1" і беремо третій елемент (індекс 2)
        prof_id = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await callback.message.answer("❌ Некоректний запит.")
        await callback.answer()
        return

    # Шукаємо професію
    stmt = select(Profession).where(Profession.id == prof_id)
    result = await session.execute(stmt)
    profession = result.scalar_one_or_none()

    if profession and profession.id_file:
        # Надсилаємо файл
        await bot.send_document(chat_id=callback.from_user.id, document=profession.id_file)
        await callback.answer("✅ Файл надіслано.")

        # Знайти користувача в БД
        stmt = select(User).where(User.user_id == callback.from_user.id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        # Якщо користувача знайдено, записуємо факт отримання файлу
        if user:
            answer = Answer(
                sms_exams=profession.name,
                sms_entered_study="Файл отримав",
                user=user
            )
            session.add(answer)
            await session.commit()
    else:
        await callback.answer("❌ Файл не знайдено або не прикріплений адміністратором.", show_alert=True)