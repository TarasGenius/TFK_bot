import os
import re
import logging
import chromadb
from chromadb.utils import embedding_functions
from config import CHROMA_DB_PATH, KNOWLEDGE_BASE_PATH

# Ініціалізація клієнта
chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
default_ef = embedding_functions.DefaultEmbeddingFunction()

collection = chroma_client.get_or_create_collection(
    name="tfk_lntu_knowledge",
    embedding_function=default_ef
)


def get_qualification(filename):
    """Визначає кваліфікацію за назвою файлу."""
    filename = filename.lower()
    if "_fmb" in filename:
        return "Фаховий молодший бакалавр (ФМБ)"
    if "_kr" in filename:
        return "Кваліфікований робітник (КР)"
    return "Загальна інформація"


def get_education_base(filename, section_text):
    """Визначає базу вступу на основі назви файлу та тексту."""
    text = section_text.lower()
    filename = filename.lower()

    if "9_class" in filename or "9 клас" in text or "базова середня освіта" in text:
        return "9 клас (БСО)"
    if "11_class" in filename or "11 клас" in text or "повна загальна" in text or "дипломів кр" in text:
        return "11 клас (ПЗСО)"

    return "Будь-яка база"


def detect_category(filename):
    """Категоризація на основі ваших назв файлів."""
    filename = filename.lower()
    if "specialties" in filename or "profession" in filename:
        return "Спеціальності та професії"
    if "document" in filename:
        return "Документи для вступу"
    if "date" in filename or "deadline" in filename or "schedule" in filename:
        return "Терміни та розклад"
    if "privilege" in filename or "benefit" in filename:
        return "Пільги"
    if "budget" in filename:
        return "Бюджетні місця"
    if "score" in filename or "exam" in filename:
        return "Іспити та бали"
    if "contact" in filename:
        return "Контакти"
    if "cabinet" in filename:
        return "Електронні кабінети"

    return "Загальне"


def split_markdown_sections(text):
    """
    Розбиває текст за заголовками від 1 до 3 рівня (## або ###).
    Це дозволить витягувати конкретні спеціальності або пункти як окремі документи.
    """
    sections = re.split(r"(?=^#{1,3}\s)", text, flags=re.MULTILINE)

    return [
        section.strip()
        for section in sections
        # Зменшено ліміт символів, щоб не губити короткі важливі списки
        if len(section.strip()) > 30
    ]


def extract_title(section):
    """Витягує назву заголовка поточного блоку."""
    match = re.search(r"^(#{1,3})\s+(.+)$", section, flags=re.MULTILINE)
    if match:
        return match.group(2).strip()
    return "Без назви"


def load_knowledge_base():
    """Завантажує файли з папки у векторну базу із додаванням мета-контексту."""
    if collection.count() > 0:
        logging.info(f"База вже містить {collection.count()} записів. Пропускаємо.")
        return

    documents, metadatas, ids = [], [], []
    if not os.path.exists(KNOWLEDGE_BASE_PATH):
        logging.error(f"Папка {KNOWLEDGE_BASE_PATH} не знайдена!")
        return

    record_id = 0
    for filename in os.listdir(KNOWLEDGE_BASE_PATH):
        if not filename.endswith(".md"):
            continue

        filepath = os.path.join(KNOWLEDGE_BASE_PATH, filename)
        with open(filepath, "r", encoding="utf-8") as file:
            text = file.read()

        qualification = get_qualification(filename)
        category = detect_category(filename)
        sections = split_markdown_sections(text)

        for section in sections:
            education_base = get_education_base(filename, section)

            # ЗБАГАЧЕННЯ КОНТЕКСТУ (RAG Best Practice):
            # Додаємо приховані підказки в текст для моделі векторизації,
            # щоб вона розуміла, про кого цей абзац, навіть якщо там немає цих слів.
            enhanced_text = (
                f"[Контекст: {qualification}, База вступу: {education_base}, Тематика: {category}]\n\n"
                f"{section}"
            )

            documents.append(enhanced_text)
            metadatas.append({
                "source": filename,
                "qualification": qualification,
                "education_base": education_base,
                "category": category,
                "section_title": extract_title(section)
            })
            ids.append(f"doc_{record_id}")
            record_id += 1

    if documents:
        collection.add(documents=documents, metadatas=metadatas, ids=ids)
        logging.info(f"Завантажено {len(documents)} секцій у Chroma.")
    else:
        logging.warning("Документи не знайдені.")


def search_in_db(query: str, n_results: int = 15) -> str:
    """Шукає релевантний контекст у базі за запитом."""
    results = collection.query(query_texts=[query], n_results=n_results)

    if results['documents'] and results['documents'][0]:
        return "\n\n---\n\n".join(results['documents'][0])
    return ""