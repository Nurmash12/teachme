import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

from .demo import DEMO_TEXT


class CardGenerationError(Exception):
    """Raised when a card provider fails or returns invalid cards."""


def get_provider_mode():
    load_dotenv()
    return os.getenv("TEACHME_MODE", "demo").strip().lower()


def _sentences(text):
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", text.strip())
        if sentence.strip()
    ]


def validate_cards(payload, text):
    if not isinstance(payload, list) or not 3 <= len(payload) <= 8:
        raise CardGenerationError("Генератор должен вернуть от 3 до 8 карточек.")

    source_sentences = set(_sentences(text))
    required_fields = {"question", "answer", "source_quote"}
    seen_questions = set()
    validated = []

    for card in payload:
        if not isinstance(card, dict) or set(card) != required_fields:
            raise CardGenerationError(
                "Карточка должна содержать только поля question, answer и source_quote."
            )

        if any(not isinstance(card[field], str) or not card[field].strip() for field in required_fields):
            raise CardGenerationError("Поля карточки не должны быть пустыми.")

        question = card["question"].strip()
        answer = card["answer"].strip()
        source_quote = card["source_quote"]
        if source_quote not in source_sentences:
            raise CardGenerationError(
                "Цитата карточки должна точно совпадать с предложением из конспекта."
            )

        question_key = question.casefold()
        if question_key in seen_questions:
            raise CardGenerationError("В генерации обнаружены повторяющиеся вопросы.")
        seen_questions.add(question_key)
        validated.append(
            {
                "question": question,
                "answer": answer,
                "source_quote": source_quote,
            }
        )

    return validated


def _generate_demo_cards(text):
    sentences = _sentences(text)
    if all(card["source_quote"] in sentences for card in DEMO_TEXT):
        return [card.copy() for card in DEMO_TEXT]
    if len(sentences) < 3:
        raise CardGenerationError(
            "Для создания карточек в DEMO-режиме нужно не менее трёх предложений."
        )

    return [
        {
            "question": f"Что говорится в конспекте: «{sentence[:80]}»?",
            "answer": sentence,
            "source_quote": sentence,
        }
        for sentence in sentences[:8]
    ]


def _generate_gemini_cards(text):
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise CardGenerationError(
            "Для режима Gemini необходимо задать GEMINI_API_KEY в файле .env."
        )

    prompt = (
        "Создай от 3 до 8 учебных карточек по данному конспекту. "
        "Верни только JSON-массив объектов с непустыми строковыми полями "
        "question, answer и source_quote. Каждая source_quote должна дословно "
        "совпадать с одним полным предложением конспекта. "
        "Не добавляй Markdown или пояснения.\n\n"
        f"Конспект:\n{text}"
    )
    request = Request(
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={api_key}",
        data=json.dumps(
            {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json"},
            }
        ).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise CardGenerationError(f"Не удалось получить ответ от Gemini: {error}") from error

    try:
        content = result["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(content)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
        raise CardGenerationError("Gemini вернул ответ в неподдерживаемом формате.") from error


def generate_cards(text):
    mode = get_provider_mode()
    if mode == "demo":
        payload = _generate_demo_cards(text)
    elif mode == "gemini":
        payload = _generate_gemini_cards(text)
    else:
        raise CardGenerationError(
            f"Неизвестный режим TEACHME_MODE: {mode or '(пусто)'}. "
            "Допустимы demo и gemini."
        )
    return validate_cards(payload, text)
