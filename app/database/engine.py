
import os
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database.models import Base
from dotenv import load_dotenv
load_dotenv()

from app.database.models import Speciality, Profession, UserProfession
from sqlalchemy import select, text

print(os.getenv('DB_LITE'))
engine = create_async_engine(url=os.getenv('DB_LITE'), echo=True)

session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def create_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def create_new_column_id_file():
    async with session_maker() as session:  # <-- ДОДАНО ()
        try:
            await session.execute(text("ALTER TABLE specialities ADD COLUMN id_file TEXT"))
            await session.commit()
            print("✅ Колонка id_file додана успішно.")
        except Exception as e:
            print(f"⚠️ Помилка: {e}")
            await session.rollback()


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
            {'name': "Кваліфікований робітник", 'call_back': 'NOL'},

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


from sqlalchemy import select


# Переконайтеся, що імпортували модель Profession
# from your_models_file import Profession

async def add_new_profession():
    print("Спроба додати нові професії...")
    # Створюємо сесію за допомогою нашої фабрики
    async with session_maker() as session:
        # Список професій, які ми хочемо додати з унікальними колбеками
        professions_data = [
            # Професії на базі 9 класів
            {'name': "Майстер діагност Слюсар КТЗ (9кл.)", 'call_back': 'MDS_KTZ_9'},
            {'name': "Е-зварювальник слюсар КТЗ (9кл.)", 'call_back': 'EZ_SKTZ_9'},
            {'name': "Е-зварювальник Сл-ремонтник (9кл.)", 'call_back': 'EZ_SR_9'},
            {'name': "Майстер діагност Сл-ремонтник (9кл.)", 'call_back': 'MD_SR_9'},
            {'name': "Кравець (9кл.)", 'call_back': 'KRAV_9'},

            # Професії на базі 11 класів
            {'name': "Флорист (11кл.)", 'call_back': 'FLOR_11'},
            {'name': "Оператор ЧПК (11кл.)", 'call_back': 'OP_CHPK_11'},
            {'name': "Слюсар колісних транспортних засобів (11кл.)", 'call_back': 'SKTZ_11'},
            {'name': "Слюсар кондиціонерів (11кл.)", 'call_back': 'SKON_11'},
        ]

        # 1. Отримуємо імена всіх існуючих професій, щоб уникнути дублікатів
        query = select(Profession.name)
        result = await session.execute(query)
        # Створюємо множину (set) для швидкого пошуку
        existing_names = {row[0] for row in result.all()}

        print(f"Існуючі професії в БД: {existing_names or 'немає'}")

        # 2. Фільтруємо список, залишаючи тільки ті, яких ще немає в базі
        new_professions_to_add = [
            Profession(name=item['name'], call_back=item['call_back'])
            for item in professions_data
            if item['name'] not in existing_names
        ]

        # 3. Якщо є що додати, додаємо їх і зберігаємо зміни
        if new_professions_to_add:
            session.add_all(new_professions_to_add)
            await session.commit()
            print(f"Успішно додано {len(new_professions_to_add)} нових професій.")
        else:
            print("Нових професій для додавання не знайдено. Всі вже існують в базі даних.")