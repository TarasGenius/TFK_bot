from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import csv

from app.database.models import User, DellUser, Speciality, UserSpeciality, Answer

async def orm_add_user(session: AsyncSession, data: dict):
    obj = User(
        user_id=data["user_id"],
        first_name=data["first_name"],
        last_name=data["last_name"],
        reg_phone=data["reg_phone"],
        teleg_phone=data["teleg_phone"],
        full_name=data["full_name"],
    )
    session.add(obj)
    await session.commit()


async def orm_del_user(session, id: int):
    try:
        stmt = (
            select(User)
            .where(User.id == id)
            .options(selectinload(User.user_specialities))
        )
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            print("⚠️ User not found for deletion")
            return False

        # Тепер user.user_specialities вже завантажені і можна ітеруватись
        speciality_names = []
        for us in user.user_specialities:
            speciality = await session.get(Speciality, us.speciality_id)
            if speciality:
                speciality_names.append(speciality.name)

        dell_user = DellUser(
            user_id=user.user_id,
            first_name=user.first_name,
            last_name=user.last_name,
            teleg_phone=user.teleg_phone,
            reg_phone=user.reg_phone,
            full_name=user.full_name,
            user_speciality=", ".join(speciality_names)
        )
        await session.delete(user)
        session.add(dell_user)
        await session.commit()
        return True

    except Exception as e:
        await session.rollback()
        print(f"❌ ERROR in orm_del_user: {e}")
        return False


async def orm_get_users(session: AsyncSession):
    query = select(User)
    result = await session.execute(query)
    return result.scalars().all()

async def orm_get_specialities(session: AsyncSession) -> list:
    """
    Повертає список всіх спеціальностей з бази даних.
    """
    query = select(Speciality)
    result = await session.execute(query)
    return result.scalars().all()

async def orm_set_user_specialities(session: AsyncSession, user_id: int, speciality_ids: list[int]):
    """
    Встановлює спеціальності для конкретного користувача.
    Спочатку видаляє старі записи, потім додає нові.
    """
    # 1. Видаляємо попередні вибори цього користувача, щоб уникнути дублікатів
    # та оновити вибір, якщо користувач вирішить його змінити.
    delete_query = delete(UserSpeciality).where(UserSpeciality.user_id == user_id)
    await session.execute(delete_query)

    # 2. Створюємо нові записи у проміжній таблиці
    # Потрібно отримати реальний ID користувача з таблиці User, а не telegram ID
    user_query = select(User.id).where(User.user_id == user_id)
    user_result = await session.execute(user_query)
    db_user_id = user_result.scalar_one_or_none()

    if db_user_id:
        new_relations = [
            UserSpeciality(user_id=db_user_id, speciality_id=spec_id)
            for spec_id in speciality_ids
        ]
        session.add_all(new_relations)
        await session.commit()


async def generate_users_csv_dump(session: AsyncSession, filename: str = 'users_dump.csv') -> str:
    print('я запустив дамп')

    # 1. Отримуємо спеціальності (Асинхронно)
    spec_result = await session.execute(select(Speciality))
    specialities = spec_result.scalars().all()

    speciality_names = [s.name for s in specialities]
    speciality_ids = [s.id for s in specialities]

    # 2. Отримуємо користувачів (Асинхронно).
    # selectinload потрібен, щоб одразу підтягнути зв'язки, інакше буде помилка MissingGreenlet
    users_result = await session.execute(
        select(User).options(selectinload(User.user_specialities))
    )
    users = users_result.scalars().all()

    # Використовуємо змінну filename замість жорстко заданої назви
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)

        # Заголовки: дані користувача + спеціальності + отримані файли (Answer)
        header = [
                     'id', 'user_id', 'first_name', 'last_name', 'teleg_phone', 'reg_phone', 'full_name'
                 ] + speciality_names + ['answers']

        writer.writerow(header)

        for user in users:
            user_speciality_ids = {us.speciality_id for us in user.user_specialities if us.speciality_id}
            speciality_columns = ['так' if sid in user_speciality_ids else 'ні' for sid in speciality_ids]

            # 3. Витягуємо всі відповіді (answers) цього користувача (Асинхронно)
            answers_result = await session.execute(
                select(Answer).filter(Answer.user_id == user.id)
            )
            answers = answers_result.scalars().all()

            # Формуємо текст із відповідей
            answers_text = "; ".join(f"{a.sms_exams}: {a.sms_entered_study}" for a in answers) if answers else ''

            row = [
                      user.id,
                      user.user_id,
                      user.first_name,
                      user.last_name,
                      user.teleg_phone,
                      user.reg_phone,
                      user.full_name
                  ] + speciality_columns + [answers_text]

            writer.writerow(row)

    # ВАЖЛИВО: повертаємо шлях до файлу, щоб бот міг його знайти і відправити
    return filename