from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import csv

from app.database.models import User, DellUser, Speciality, UserSpeciality, Answer, Profession, UserProfession

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
        # 1. Одразу підтягуємо і спеціальності, і професії разом з їхніми таблицями,
        # щоб уникнути зайвих запитів до БД у циклі
        stmt = (
            select(User)
            .where(User.id == id)
            .options(
                selectinload(User.user_specialities).selectinload(UserSpeciality.speciality),
                selectinload(User.user_professions).selectinload(UserProfession.profession)
            )
        )
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            print("⚠️ User not found for deletion")
            return False

        # 2. Формуємо списки назв без додаткових запитів
        speciality_names = [us.speciality.name for us in user.user_specialities if us.speciality]
        profession_names = [up.profession.name for up in user.user_professions if up.profession]

        # 3. Оскільки в моделі DellUser є лише колонка user_speciality,
        # ми об'єднуємо вибір користувача в один красивий текстовий рядок для архіву
        saved_info = []
        if speciality_names:
            saved_info.append(f"ФМБ: {', '.join(speciality_names)}")
        if profession_names:
            saved_info.append(f"КР: {', '.join(profession_names)}")

        archived_text = " | ".join(saved_info)

        # 4. Створюємо архівний запис
        dell_user = DellUser(
            user_id=user.user_id,
            first_name=user.first_name,
            last_name=user.last_name,
            teleg_phone=user.teleg_phone,
            reg_phone=user.reg_phone,
            full_name=user.full_name,
            user_speciality=archived_text
        )

        # 5. Видаляємо користувача (усі пов'язані записи видаляться автоматично завдяки cascade="all, delete-orphan")
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



async def orm_get_professions(session: AsyncSession) -> list:
    """
    Повертає список всіх професій з бази даних.
    """
    query = select(Profession)
    result = await session.execute(query)
    return result.scalars().all()


async def orm_set_user_professions(session: AsyncSession, user_id: int, profession_ids: list[int]):
    """
    Встановлює професії для конкретного користувача.
    Спочатку видаляє старі записи, потім додає нові.
    """
    # 1. Потрібно отримати реальний ID користувача з таблиці User (за його Telegram ID)
    user_query = select(User.id).where(User.user_id == user_id)
    user_result = await session.execute(user_query)
    db_user_id = user_result.scalar_one_or_none()

    if db_user_id:
        # 2. Видаляємо попередні вибори цього користувача, щоб уникнути дублікатів.
        # Використовуємо db_user_id, оскільки UserProfession.user_id посилається на users.id
        delete_query = delete(UserProfession).where(UserProfession.user_id == db_user_id)
        await session.execute(delete_query)

        # 3. Створюємо нові записи у проміжній таблиці
        new_relations = [
            UserProfession(user_id=db_user_id, profession_id=prof_id)
            for prof_id in profession_ids
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


async def generate_professions_csv_dump(session: AsyncSession, filename: str = 'professions_dump.csv') -> str:
    print('я запустив дамп професій')

    # 1. Отримуємо професії (Асинхронно)
    prof_result = await session.execute(select(Profession))
    professions = prof_result.scalars().all()

    profession_names = [p.name for p in professions]
    profession_ids = [p.id for p in professions]

    # 2. Отримуємо користувачів (Асинхронно).
    # selectinload підтягує зв'язки з таблицею user_professions
    users_result = await session.execute(
        select(User).options(selectinload(User.user_professions))
    )
    users = users_result.scalars().all()

    # Використовуємо змінну filename
    with open(filename, 'w', newline='', encoding='utf-8-sig') as f:  # utf-8-sig краще для Excel
        writer = csv.writer(f,
                            delimiter=';')  # delimiter=';' часто зручніший для Excel в нашому регіоні, але можете змінити на ','

        # Заголовки: дані користувача + професії + отримані файли (Answer)
        header = [
                     'id', 'user_id', 'first_name', 'last_name', 'teleg_phone', 'reg_phone', 'full_name'
                 ] + profession_names + ['answers']

        writer.writerow(header)

        for user in users:
            # Витягуємо ID професій, які обрав цей користувач
            user_profession_ids = {up.profession_id for up in user.user_professions if up.profession_id}

            # Проставляємо "так" або "ні" для кожної професії
            profession_columns = ['так' if pid in user_profession_ids else 'ні' for pid in profession_ids]

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
                  ] + profession_columns + [answers_text]

            writer.writerow(row)

    # ВАЖЛИВО: повертаємо шлях до файлу, щоб бот міг його знайти і відправити
    return filename

