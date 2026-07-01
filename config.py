import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Ключі
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


START_ANSWER = ('Привіт, якщо зареєструєшся через /register я буду сповіщати тебе про екзамени.'
                ' Задавай питання розкажу все що знаю про вступ, але можу трошки довго думати! ')


SPECIALITY = {
    "Комп'ютерна інженерія": 'KI',
    "Дизайн": 'DZ',
    "Менеджмент": 'MD',
    "Інформаційні системи та технології": 'ICT',
    "Електроенергетика": 'ET',
    "Автомобільний транспорт": 'AT',
    "Кібербезпека": 'KB',
    "Транспортні технології": 'TT',
    "Підприємництво": 'PT'

}
BASE_DIR = Path(__file__).resolve().parent


KNOWLEDGE_BASE_PATH = str(BASE_DIR / "app" / "knowledge_base")
CHROMA_DB_PATH = str(BASE_DIR / "app" / "knowledge_base")
print(KNOWLEDGE_BASE_PATH, CHROMA_DB_PATH)