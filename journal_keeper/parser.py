"""
Парсер записей дневника в формате ===...===.
Извлекает структурированные данные из текстового блока.
"""

import re
from datetime import date
from typing import Optional


def parse_entry_block(block: str) -> Optional[dict]:
    """
    Парсит один блок записи в формате ===...===.

    Вход: строка с блоком записи.
    Выход: словарь с ключами date, time, topic, mood, text, tags, extra, raw_dump
           или None, если блок невалиден (пустой ТЕКСТ).

    Формат блока:
    ===
    ДАТА: ГГГГ-ММ-ДД
    ВРЕМЯ: ЧЧ:ММ (опционально)
    ТЕМА: строка
    ТЭГИ: слово1, слово2, слово3
    НАСТРОЕНИЕ: слово
    ТЕКСТ: многострочный текст
    ---
    ДОП_ПОЛЯ: любая информация
    ===
    """
    if not block or not block.strip():
        return None

    # Нормализуем — убираем ведущие/хвостовые разделители ===
    content = block.strip()
    content = re.sub(r"^===+\s*", "", content)
    content = re.sub(r"\s*===+\s*$", "", content)
    content = content.strip()

    result = {
        "date": "",
        "time": None,
        "topic": "",
        "mood": "",
        "text": "",
        "tags": [],
        "extra": {},
        "raw_dump": block.strip(),
    }

    # Стандартные поля, которые мы знаем
    known_fields = {"ДАТА", "ВРЕМЯ", "ТЕМА", "ТЭГИ", "НАСТРОЕНИЕ", "ТЕКСТ"}

    # Разделяем на основную часть и доп. поля (после ---)
    parts = re.split(r"\n\s*---\s*\n", content, maxsplit=1)
    main_part = parts[0]
    extra_part = parts[1] if len(parts) > 1 else ""

    # Парсим доп. поля
    if extra_part.strip():
        for line in extra_part.strip().splitlines():
            line = line.strip()
            if ":" in line:
                key, _, value = line.partition(":")
                result["extra"][key.strip()] = value.strip()

    # Парсим основную часть
    # Сперва извлечём ТЕКСТ — всё после строки "ТЕКСТ:" до конца основной части
    text_match = re.search(r"(?mi)^ТЕКСТ:\s*(.*)", main_part, re.DOTALL)
    if text_match:
        text_content = text_match.group(1).strip()
        # Убираем из текста хвостовые строки доп. полей (если --- не было)
        result["text"] = text_content
        # Удаляем ТЕКСТ из main_part для парсинга остальных полей
        main_part_before_text = main_part[: text_match.start()]
    else:
        main_part_before_text = main_part
        # Если ТЕКСТ не найден как заголовок, возможно весь блок — текст
        # Проверяем, есть ли вообще какие-то поля
        has_known_field = any(
            re.search(rf"(?mi)^{field}:", main_part) for field in known_fields
        )
        if not has_known_field:
            result["text"] = content
        else:
            result["text"] = ""

    # Парсим остальные поля из части перед ТЕКСТ
    for line in main_part_before_text.splitlines():
        line = line.strip()
        if not line:
            continue

        if ":" not in line:
            continue

        key, _, value = line.partition(":")
        key = key.strip().upper()
        value = value.strip()

        if key == "ДАТА":
            result["date"] = value
        elif key == "ВРЕМЯ":
            result["time"] = value if value else None
        elif key == "ТЕМА":
            result["topic"] = value
        elif key == "ТЭГИ" or key == "ТЕГИ":
            # Поддержка обоих вариантов написания
            if value:
                result["tags"] = [
                    t.strip().lower()
                    for t in re.split(r"[,;，；\s]+", value)
                    if t.strip()
                ]
        elif key == "НАСТРОЕНИЕ":
            result["mood"] = value

    # Если дата не указана — подставить текущую
    if not result["date"]:
        result["date"] = date.today().isoformat()

    # Валидация: если ТЕКСТ пуст — запись невалидна
    if not result["text"].strip():
        return None

    return result


def extract_blocks_from_text(text: str) -> list[str]:
    """
    Извлекает все блоки ===...=== из произвольного текста.
    Возвращает список строк (каждая — один блок с разделителями ===).
    """
    # Ищем блоки между строками === (три и более знака равно)
    pattern = r"(===+\s*\n.*?\n\s*===+)"
    blocks = re.findall(pattern, text, re.DOTALL)
    return blocks
