
import os
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database.models import Base
from dotenv import load_dotenv
load_dotenv()

from app.database.models import Speciality
from sqlalchemy import select

print(os.getenv('DB_LITE'))
engine = create_async_engine(url=os.getenv('DB_LITE'), echo=True)

session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def create_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)




async def add_new_speciality():
    print("Спроба додати нові спеціальності...")
    # Створюємо сесію за допомогою нашої фабрики
    async with session_maker() as session:
        # Список спеціальностей, які ми хочемо додати
        specialities_data = [
            {'name': "Комп'ютерна інженерія", 'call_back': 'KI'},
            {'name': "Інформаційні системи та технології", 'call_back': 'ICT'},
            {'name': "Кібербезпека", 'call_back': 'KB'},
            {'name': "Дизайн", 'call_back': 'DZ'},
            {'name': "Менеджмент", 'call_back': 'MD'},
            {'name': "Електроенергетика", 'call_back': 'ET'},
            {'name': "Автомобільний транспорт", 'call_back': 'AT'},
            {'name': "Транспортні технології", 'call_back': 'TT'},
            {'name': "Підприємництво", 'call_back': 'PT'},

        ]

        # 1. Отримуємо імена всіх існуючих спеціальностей, щоб уникнути дублікатів
        query = select(Speciality.name)
        result = await session.execute(query)
        # Створюємо множину (set) для швидкого пошуку
        existing_names = {row[0] for row in result.all()}

        print(f"Існуючі спеціальності в БД: {existing_names or 'немає'}")

        # 2. Фільтруємо список, залишаючи тільки ті, яких ще немає в базі
        new_specialities_to_add = [
            Speciality(name=item['name'], call_back=item['call_back'])
            for item in specialities_data
            if item['name'] not in existing_names
        ]

        # 3. Якщо є що додати, додаємо їх і зберігаємо зміни
        if new_specialities_to_add:
            session.add_all(new_specialities_to_add)
            await session.commit()
            print(f"Успішно додано {len(new_specialities_to_add)} нових спеціальностей.")
        else:
            print("Нових спеціальностей для додавання не знайдено. Всі вже існують в базі даних.")
