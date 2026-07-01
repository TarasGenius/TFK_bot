import logging
from aiogram import Router
from aiogram.types import Message

from app.services.vector_db import search_in_db
from app.services.ai_service import generate_consultation_response


ai_router = Router()

user_histories = {}
MAX_HISTORY_LENGTH = 20

@ai_router.message()
async def handle_questions(message: Message, bot):
    user_query = message.text
    user_id = message.from_user.id

    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    wait_msg = await message.answer("⏳ Думаю... Це може зайняти трішки часу.")

    try:
        if user_id not in user_histories:
            user_histories[user_id] = []

            # 2. Формуємо текст історії для промпту
        history_text = "\n".join(user_histories[user_id])
        if history_text:
            history_context = f"\nІСТОРІЯ ПОПЕРЕДНЬОГО ДІАЛОГУ:\n{history_text}\n"
        else:
            history_context = ""

        search_query = user_query

        if user_id in user_histories and user_histories[user_id]:
            # 1. Витягуємо З УСІЄЇ історії ТІЛЬКИ запитання абітурієнта
            # (відкидаємо відповіді бота та префікси)
            user_questions = [
                msg.replace("Абітурієнт: ", "")
                for msg in user_histories[user_id]
                if msg.startswith("Абітурієнт:")
            ]

            # 2. Вказуємо, скільки попередніх запитань брати (наприклад, останні 2)
            HISTORY_DEPTH = 2
            recent_questions = user_questions[-HISTORY_DEPTH:]

            if recent_questions:
                # З'єднуємо крапкою з пробілом
                context_string = ". ".join(recent_questions)
                search_query = f"{context_string}. {user_query}"

        # Крок А: Шукаємо контекст у базі
        retrieved_context = search_in_db(search_query)

        # Крок Б: Генеруємо відповідь
        response_text = await generate_consultation_response(user_query, retrieved_context, history_context)

        user_histories[user_id].append(f"Абітурієнт: {user_query}")
        user_histories[user_id].append(f"Бот: {response_text}")

        # Обрізаємо список, якщо він перевищив ліміт (залишаємо тільки останні MAX_HISTORY_LENGTH елементів)
        if len(user_histories[user_id]) > MAX_HISTORY_LENGTH:
            user_histories[user_id] = user_histories[user_id][-MAX_HISTORY_LENGTH:]

        try:
            await wait_msg.edit_text(response_text, parse_mode="Markdown")
        except Exception as telegram_parse_error:
            logging.warning(f"Помилка розмітки: {telegram_parse_error}. Відправка простим текстом.")
            await wait_msg.edit_text(response_text)


    except Exception as e:
        logging.error(f"Помилка під час обробки: {e}")
        await wait_msg.edit_text(
            "Вибачте, виникла технічна заминка під час пошуку інформації. Спробуйте повторити запит трохи пізніше."
        )