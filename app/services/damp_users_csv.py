from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import User, Speciality, Answer  # або твоя назва файла з моделями
import os
import csv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
db_path = os.path.join(BASE_DIR, "db.sqlite3")
engine = create_engine(f"sqlite:///{db_path}")
Session = sessionmaker(bind=engine)
session = Session()

specialities = session.query(Speciality).all()
speciality_names = [s.name for s in specialities]
speciality_ids = [s.id for s in specialities]

users = session.query(User).all()

with open('users_dump.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)

    # Заголовки: дані користувача + спеціальності + отримані файли (Answer)
    header = [
        'id', 'user_id', 'first_name', 'last_name', 'teleg_phone', 'reg_phone', 'full_name'
    ] + speciality_names + ['answers']

    writer.writerow(header)

    for user in users:
        user_speciality_ids = {us.speciality_id for us in user.user_specialities if us.speciality_id}

        speciality_columns = ['так' if sid in user_speciality_ids else 'ні' for sid in speciality_ids]

        # Витягнути всі відповіді (answers) цього користувача
        answers = session.query(Answer).filter(Answer.user_id == user.id).all()

        # Формуємо текст із відповідей у форматі: "Назва спеціальності: Статус", розділені крапкою з комою
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

print(f"✅ Дамп сформовано")