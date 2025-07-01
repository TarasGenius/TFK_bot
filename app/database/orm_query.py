from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import User, DellUser, Speciality, UserSpeciality

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
