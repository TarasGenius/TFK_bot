import os
import tempfile
import pandas as pd
from docx import Document
from docxcompose.composer import Composer
from docxtpl import DocxTemplate
import pymorphy3

morph = pymorphy3.MorphAnalyzer(lang='uk')



def decline_word(text, case):
    """Просте відмінювання (для міст, посад, звичайних слів)."""
    words = str(text).split()
    if not words: return ""
    declined_words = []
    for word in words:
        parsed = morph.parse(word)[0]
        try:
            declined_words.append(parsed.inflect({case}).word.title())
        except AttributeError:
            declined_words.append(word.title())
    return " ".join(declined_words)


def decline_pib(full_name, case):
    """Складна логіка для ПІБ із врахуванням статі та невідмінюваних жіночих прізвищ."""
    words = str(full_name).split()
    if not words: return ""

    gender = None
    last_word = words[-1].lower()
    if last_word.endswith('ич'):
        gender = 'masc'
    elif last_word.endswith('на'):
        gender = 'femn'

    declined_words = []

    for i, word in enumerate(words):
        if i == 0 and gender == 'femn' and word[-1].lower() not in 'ая':
            declined_words.append(word.title())
            continue

        parses = morph.parse(word)
        best_parse = parses[0]

        for p in parses:
            if 'anim' in p.tag:
                if gender and gender in p.tag:
                    best_parse = p
                    break
                elif not gender:
                    best_parse = p
                    break
        try:
            inflected = best_parse.inflect({case})
            if inflected:
                declined_words.append(inflected.word.title())
            else:
                declined_words.append(word.title())
        except Exception:
            declined_words.append(word.title())

    return " ".join(declined_words)


def generate_merged_document(template_path: str, csv_path: str, declension_rules: dict) -> str:
    """Генерація документів і склеювання."""
    df = pd.read_csv(csv_path)
    records = df.to_dict(orient='records')

    temp_dir = tempfile.mkdtemp()
    generated_files = []

    for index, row in enumerate(records):
        doc = DocxTemplate(template_path)
        context = {}

        for col_name, value in row.items():
            if pd.isna(value):
                value = ""

            target_case = declension_rules.get(col_name)

            # Якщо користувач вибрав якийсь відмінок (не "none")
            if target_case and target_case != 'none':
                # Перевіряємо, чи колонка містить "name", "піб" або "ім'я"
                col_lower = str(col_name).lower()
                if 'name' in col_lower or 'піб' in col_lower or "ім'я" in col_lower:
                    context[col_name] = decline_pib(value, target_case)
                else:
                    context[col_name] = decline_word(value, target_case)
            else:
                # Залишаємо без змін
                context[col_name] = str(value)

        doc.render(context)

        temp_file_path = os.path.join(temp_dir, f"temp_{index}.docx")
        doc.save(temp_file_path)
        generated_files.append(temp_file_path)

    master_doc = Document(generated_files[0])
    if len(generated_files) > 1:
        master_doc.add_page_break()

    composer = Composer(master_doc)

    for file_path in generated_files[1:]:
        doc_to_append = Document(file_path)
        composer.append(doc_to_append)
        if file_path != generated_files[-1]:
            composer.doc.add_page_break()

    final_output_path = tempfile.mktemp(suffix=".docx", prefix="Result_")
    composer.save(final_output_path)

    for f in generated_files:
        os.remove(f)

    return final_output_path