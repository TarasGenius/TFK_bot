from aiogram import Router, F
from aiogram.filters.callback_data import CallbackData
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import START_ANSWER
from app.database.models import Speciality, User, Answer
from app.database.orm_query import orm_add_user, orm_get_specialities, orm_set_user_specialities

user_router = Router()

@user_router.message(CommandStart())
async def start_cmd(message: Message):
    await message.answer(text=START_ANSWER)



# class Register(StatesGroup):
#     full_name = State()
#     reg_phone = State()
#
#
#
# # FSM register
# @user_router.message(Command('register'))
# async def register(message: Message, state: FSMContext):
#     await state.set_state(Register.full_name)
#     await message.answer('Введіть повне ім\'я(ПІБ)')
#
#
# @user_router.message(Register.full_name)
# async def register_second_step(message: Message, state: FSMContext):
#     await state.update_data(full_name=message.text)
#     await state.set_state(Register.reg_phone)
#     await message.answer('Введіть номер телефону(0661234567)')
#
#
# @user_router.message(Register.reg_phone)
# async def register_third_step(message: Message, state: FSMContext, session: AsyncSession):
#     await state.update_data(reg_phone=message.text)
#     data = await state.get_data()
#     data['user_id'] = message.from_user.id
#     data['first_name'] = message.from_user.first_name
#     data['last_name'] = message.from_user.last_name
#     data['teleg_phone'] = None
#     try:
#         await orm_add_user(session=session, data=data)
#     except IntegrityError:
#         await message.answer('Ви вже зареєстровані')
#     else:
#         await message.answer(f'Реєстрацію завершено. Імя {data["full_name"]}')
#     finally:
#         await state.clear()
#
#
# class ChooseSpeciality(StatesGroup):
#     choosing = State()
#
#
# # Фабрика Callback'ів для керування кнопками
# class SpecialityCallback(CallbackData, prefix="spec"):
#     action: str  # 'select' або 'confirm'
#     speciality_id: int | None = None  # ID спеціальності, None для кнопки "Підтвердити"
#
#
# # Функція для створення динамічної клавіатури
# async def create_specialities_keyboard(
#         specialities: list[Speciality],
#         selected: list[int]
# ) -> InlineKeyboardMarkup:  # ВИПРАВЛЕНО: тип повернення змінено на InlineKeyboardMarkup
#     builder = InlineKeyboardBuilder()
#     for spec in specialities:
#         text = f"✅ {spec.name}" if spec.id in selected else spec.name
#         builder.button(
#             text=text,
#             callback_data=SpecialityCallback(action="select", speciality_id=spec.id).pack()
#         )
#     # Робимо кнопки в один стовпчик
#     builder.adjust(1)
#
#     # ВИПРАВЛЕНО: Метод .row() очікує об'єкт кнопки, а не виклик builder.button()
#     # Створюємо кнопку явно через InlineKeyboardButton
#     builder.row(
#         InlineKeyboardButton(
#             text="Підтвердити вибір",
#             callback_data=SpecialityCallback(action="confirm").pack()
#         )
#     )
#     return builder.as_markup()
#
#
# # Хендлер, що запускає процес вибору
# @user_router.message(Command('specialities'))
# async def choose_specialities_start(message: Message, state: FSMContext, session: AsyncSession):
#     specialities = await orm_get_specialities(session)
#     if not specialities:
#         await message.answer("На жаль, наразі немає доступних спеціальностей.")
#         return
#
#     await state.set_state(ChooseSpeciality.choosing)
#     # Зберігаємо в FSM початковий порожній список вибору
#     await state.update_data(selected_ids=[])
#
#     keyboard = await create_specialities_keyboard(specialities, [])
#     await message.answer("Оберіть одну або декілька спеціальностей, за якими хочете отримувати сповіщення:",
#                          reply_markup=keyboard)
#
#
# # Обробник натискання на кнопку спеціальності
# @user_router.callback_query(ChooseSpeciality.choosing, SpecialityCallback.filter(F.action == "select"))
# async def process_speciality_select(callback: CallbackQuery, callback_data: SpecialityCallback, state: FSMContext,
#                                     session: AsyncSession):
#     data = await state.get_data()
#     selected_ids = data.get("selected_ids", [])
#     spec_id = callback_data.speciality_id
#
#     if spec_id in selected_ids:
#         selected_ids.remove(spec_id)
#     else:
#         selected_ids.append(spec_id)
#
#     await state.update_data(selected_ids=selected_ids)
#
#     specialities = await orm_get_specialities(session)
#     keyboard = await create_specialities_keyboard(specialities, selected_ids)
#
#     # Оновлюємо клавіатуру, не надсилаючи нове повідомлення
#     await callback.message.edit_reply_markup(reply_markup=keyboard)
#     await callback.answer()  # Обов'язково відповідаємо на callback
#
#
# # Обробник натискання на кнопку "Підтвердити"
# @user_router.callback_query(ChooseSpeciality.choosing, SpecialityCallback.filter(F.action == "confirm"))
# async def process_speciality_confirm(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
#     data = await state.get_data()
#     selected_ids = data.get("selected_ids", [])
#
#     if not selected_ids:
#         await callback.answer("Ви не обрали жодної спеціальності.", show_alert=True)
#         return
#
#     await orm_set_user_specialities(session, user_id=callback.from_user.id, speciality_ids=selected_ids)
#
#     await callback.message.edit_text("Ваш вибір збережено! Ми будемо надсилати вам актуальну інформацію.")
#     await callback.answer()
#     await state.clear()


# Оновлений клас станів (додано стан для вибору спеціальностей)
class Register(StatesGroup):
    full_name = State()
    reg_phone = State()
    choosing_speciality = State()  # Новий стан


# Фабрика Callback'ів
class SpecialityCallback(CallbackData, prefix="spec"):
    action: str
    speciality_id: int | None = None


# Функція створення клавіатури (залишається без змін)
async def create_specialities_keyboard(
        specialities: list,  # Замініть на list[Speciality] якщо у вас є імпорт моделі
        selected: list[int]
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for spec in specialities:
        text = f"✅ {spec.name}" if spec.id in selected else spec.name
        builder.button(
            text=text,
            callback_data=SpecialityCallback(action="select", speciality_id=spec.id).pack()
        )
    builder.adjust(1)
    builder.row(
        InlineKeyboardButton(
            text="Підтвердити вибір",
            callback_data=SpecialityCallback(action="confirm").pack()
        )
    )
    return builder.as_markup()


# 1. Початок реєстрації
@user_router.message(Command('register'))
async def register(message: Message, state: FSMContext):
    await state.set_state(Register.full_name)
    await message.answer("Введіть повне ім'я(ПІБ)")


# 2. Введення імені
@user_router.message(Register.full_name)
async def register_second_step(message: Message, state: FSMContext):
    await state.update_data(full_name=message.text)
    await state.set_state(Register.reg_phone)
    await message.answer('Введіть номер телефону(0661234567)')


# 3. Введення телефону -> Перехід до вибору спеціальностей
@user_router.message(Register.reg_phone)
async def register_third_step(message: Message, state: FSMContext, session: AsyncSession):
    await state.update_data(reg_phone=message.text)

    # Отримуємо спеціальності з БД
    specialities = await orm_get_specialities(session)
    if not specialities:
        await message.answer("На жаль, наразі немає доступних спеціальностей для вибору.")
        await state.clear()
        return

    # Переходимо на новий етап FSM
    await state.set_state(Register.choosing_speciality)
    await state.update_data(selected_ids=[])  # Пустий список вибору

    keyboard = await create_specialities_keyboard(specialities, [])
    await message.answer("Оберіть одну або декілька спеціальностей:", reply_markup=keyboard)


# 4. Обробка натискання на спеціальність
@user_router.callback_query(Register.choosing_speciality, SpecialityCallback.filter(F.action == "select"))
async def process_speciality_select(callback: CallbackQuery, callback_data: SpecialityCallback, state: FSMContext,
                                    session: AsyncSession):
    data = await state.get_data()
    selected_ids = data.get("selected_ids", [])
    spec_id = callback_data.speciality_id

    if spec_id in selected_ids:
        selected_ids.remove(spec_id)
    else:
        selected_ids.append(spec_id)

    await state.update_data(selected_ids=selected_ids)

    specialities = await orm_get_specialities(session)
    keyboard = await create_specialities_keyboard(specialities, selected_ids)

    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()


# 5. Підтвердження вибору та фінальне збереження в БД
@user_router.callback_query(Register.choosing_speciality, SpecialityCallback.filter(F.action == "confirm"))
async def process_speciality_confirm(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    selected_ids = data.get("selected_ids", [])

    if not selected_ids:
        await callback.answer("Ви не обрали жодної спеціальності.", show_alert=True)
        return

    # Формуємо дані користувача для збереження
    user_data = {
        'user_id': callback.from_user.id,
        'first_name': callback.from_user.first_name,
        'last_name': callback.from_user.last_name,
        'full_name': data.get('full_name'),
        'reg_phone': data.get('reg_phone'),
        'teleg_phone': None
    }

    try:
        # Спочатку створюємо користувача
        await orm_add_user(session=session, data=user_data)

        # Потім прив'язуємо обрані спеціальності
        await orm_set_user_specialities(session, user_id=callback.from_user.id, speciality_ids=selected_ids)

    except IntegrityError:
        await callback.message.edit_text("❌ Ви вже зареєстровані.")
    else:
        await callback.message.edit_text(
            f"✅ Реєстрацію завершено! Ваше ім'я: {user_data['full_name']}.\nСпеціальності успішно збережено.")
    finally:
        await state.clear()

    await callback.answer()




@user_router.callback_query(F.data.startswith("getfile_"))
async def send_requested_file(callback: CallbackQuery, session: AsyncSession, bot):
    try:
        spec_id = int(callback.data.split("_")[1])
    except (IndexError, ValueError):
        await callback.message.answer("❌ Некоректний запит.")
        return

    stmt = select(Speciality).where(Speciality.id == spec_id)
    result = await session.execute(stmt)
    speciality = result.scalar_one_or_none()

    if speciality and speciality.id_file:
        await bot.send_document(chat_id=callback.from_user.id, document=speciality.id_file)
        await callback.answer("✅ Файл надіслано.")

        # Знайти користувача в БД
        stmt = select(User).where(User.user_id == callback.from_user.id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        # Якщо користувача знайдено, записуємо факт отримання файлу
        if user:
            answer = Answer(
                sms_exams=speciality.name,
                sms_entered_study="Файл отримав",
                user=user
            )
            session.add(answer)
            await session.commit()
    else:
        await callback.answer("❌ Файл не знайдено або не прикріплений адміністратором.")
