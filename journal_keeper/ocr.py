"""
Модуль OCR — распознавание рукописного текста с изображений.
Гибридная стратегия: сначала локальный движок, при низкой уверенности
или по запросу — внешний API.

Поддерживаемые движки (выбор через переменную окружения OCR_ENGINE):
- easyocr: рекомендуется для рукописного текста (локальный)
- tesseract: требует установки Tesseract OCR (локальный)
- gemini: Google Gemini API (внешний)
- zai: Z.ai GLM-4.6V / GLM-5V-Turbo (внешний)
"""

import base64
import sys
from pathlib import Path
from typing import Optional

from .config import (
    get_gemini_api_key,
    get_ocr_confidence_threshold,
    get_ocr_engine,
    get_zai_api_key,
)


def recognize_image(
    image_path: str,
    engine: Optional[str] = None,
    fallback_to_external: bool = True,
) -> str:
    """
    Распознаёт рукописный текст на изображении.

    Параметры:
        image_path: путь к файлу изображения (JPEG, PNG)
        engine: движок OCR (если None — берётся из конфигурации)
        fallback_to_external: при низкой уверенности локального движка
                              попробовать внешний API

    Возвращает:
        Строку с распознанным текстом без изменений (орфография, регистр,
        переносы строк сохраняются). Пустую строку, если текст не найден.
    """
    path = Path(image_path)
    if not path.exists():
        print(f"[ОШИБКА] Файл не найден: {image_path}", file=sys.stderr)
        return ""

    if not path.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"):
        print(
            f"[ОШИБКА] Неподдерживаемый формат: {path.suffix}. "
            "Поддерживаются: JPEG, PNG, BMP, TIFF, WebP",
            file=sys.stderr,
        )
        return ""

    engine_name = engine or get_ocr_engine()
    engine_name = engine_name.lower().strip()

    # Локальные движки
    if engine_name == "easyocr":
        text, confidence = _recognize_easyocr(str(path))
        if text.strip() and confidence >= get_ocr_confidence_threshold():
            return text
        if fallback_to_external and text.strip():
            print(
                f"[ИНФО] Уверенность EasyOCR низкая ({confidence:.2f}). "
                "Рекомендуется повторить с внешним движком (gemini/zai)."
            )
        return text

    elif engine_name == "tesseract":
        text, confidence = _recognize_tesseract(str(path))
        if text.strip() and confidence >= get_ocr_confidence_threshold():
            return text
        if fallback_to_external and text.strip():
            print(
                f"[ИНФО] Уверенность Tesseract низкая ({confidence:.2f}). "
                "Рекомендуется повторить с внешним движком (gemini/zai)."
            )
        return text

    # Внешние движки
    elif engine_name == "gemini":
        return _recognize_gemini(str(path))

    elif engine_name == "zai":
        return _recognize_zai(str(path))

    else:
        print(
            f"[ОШИБКА] Неизвестный OCR-движок: {engine_name}. "
            "Доступные: easyocr, tesseract, gemini, zai",
            file=sys.stderr,
        )
        return ""


def _recognize_easyocr(image_path: str) -> tuple[str, float]:
    """
    Распознавание через EasyOCR (локальный).
    Возвращает (текст, средняя_уверенность).
    """
    try:
        import easyocr

        # Поддержка русского и английского
        reader = easyocr.Reader(["ru", "en"], gpu=False)
        results = reader.readtext(image_path)

        if not results:
            return "", 0.0

        lines = []
        confidences = []
        for bbox, text, conf in results:
            lines.append(text)
            confidences.append(conf)

        full_text = "\n".join(lines)
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        return full_text, avg_confidence

    except ImportError:
        print(
            "[ПРЕДУПРЕЖДЕНИЕ] EasyOCR не установлен. Установите: pip install easyocr",
            file=sys.stderr,
        )
        return "", 0.0
    except Exception as e:
        print(
            f"[ОШИБКА] EasyOCR: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return "", 0.0


def _recognize_tesseract(image_path: str) -> tuple[str, float]:
    """
    Распознавание через Tesseract (локальный).
    Возвращает (текст, средняя_уверенность).
    """
    try:
        import pytesseract
        from PIL import Image

        img = Image.open(image_path)
        # Русский + английский, режим для рукописного текста
        text = pytesseract.image_to_string(img, lang="rus+eng")

        # Получаем уверенность через image_to_data
        data = pytesseract.image_to_data(img, lang="rus+eng", output_type=pytesseract.Output.DICT)
        confidences = [
            int(c) for c in data["conf"] if int(c) > 0
        ]
        avg_confidence = (sum(confidences) / len(confidences) / 100.0) if confidences else 0.0

        return text.strip(), avg_confidence

    except ImportError:
        print(
            "[ПРЕДУПРЕЖДЕНИЕ] pytesseract не установлен. Установите: pip install pytesseract",
            file=sys.stderr,
        )
        return "", 0.0
    except Exception as e:
        print(
            f"[ОШИБКА] Tesseract: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return "", 0.0


def _recognize_gemini(image_path: str) -> str:
    """
    Распознавание через Google Gemini API (внешний).
    Требует GEMINI_API_KEY в переменных окружения.
    """
    api_key = get_gemini_api_key()
    if not api_key:
        print(
            "[ОШИБКА] GEMINI_API_KEY не задан. Установите переменную окружения.",
            file=sys.stderr,
        )
        return ""

    try:
        import google.generativeai as genai
        from PIL import Image

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")

        img = Image.open(image_path)

        prompt = (
            "Выведи только распознанный рукописный текст с изображения. "
            "Никаких пояснений, исправлений, комментариев или обёрток. "
            "Сохрани оригинальную орфографию, регистр и переносы строк."
        )

        response = model.generate_content([prompt, img])
        return response.text.strip() if response.text else ""

    except ImportError:
        print(
            "[ПРЕДУПРЕЖДЕНИЕ] google-generativeai не установлен. "
            "Установите: pip install google-generativeai",
            file=sys.stderr,
        )
        return ""
    except Exception as e:
        print(
            f"[ОШИБКА] Gemini API: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return ""


def _recognize_zai(image_path: str) -> str:
    """
    Распознавание через Z.ai API (GLM-4.6V / GLM-5V-Turbo).
    Требует ZAI_API_KEY в переменных окружения.
    """
    api_key = get_zai_api_key()
    if not api_key:
        print(
            "[ОШИБКА] ZAI_API_KEY не задан. Установите переменную окружения.",
            file=sys.stderr,
        )
        return ""

    try:
        import httpx
        from PIL import Image

        # Кодируем изображение в base64
        img = Image.open(image_path)
        import io

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG")
        img_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        prompt = (
            "Выведи только распознанный рукописный текст с изображения. "
            "Никаких пояснений, исправлений, комментариев или обёрток. "
            "Сохрани оригинальную орфографию, регистр и переносы строк."
        )

        # Вызов Z.ai API (совместимый с OpenAI формат)
        response = httpx.post(
            "https://open.bigmodel.cn/api/paas/v4/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "glm-4v-flash",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{img_b64}"
                                },
                            },
                        ],
                    }
                ],
            },
            timeout=60.0,
        )

        if response.status_code == 200:
            data = response.json()
            return (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
        else:
            print(
                f"[ОШИБКА] Z.ai API вернул статус {response.status_code}: "
                f"{response.text}",
                file=sys.stderr,
            )
            return ""

    except ImportError:
        print(
            "[ПРЕДУПРЕЖДЕНИЕ] httpx не установлен. Установите: pip install httpx",
            file=sys.stderr,
        )
        return ""
    except Exception as e:
        print(
            f"[ОШИБКА] Z.ai API: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return ""
