"""
Конфигурация системы через переменные окружения.
"""

import os
from pathlib import Path


def get_db_path() -> str:
    """Путь к файлу SQLite. По умолчанию ~/.journal_keeper.db"""
    return os.environ.get("DB_PATH", str(Path.home() / ".journal_keeper.db"))


def get_ollama_model() -> str:
    """Имя модели Ollama для редактора. По умолчанию deepseek-r1:7b"""
    return os.environ.get("OLLAMA_MODEL", "deepseek-r1:7b")


def get_ocr_engine() -> str:
    """Движок OCR: easyocr, tesseract, gemini, zai. По умолчанию easyocr"""
    return os.environ.get("OCR_ENGINE", "easyocr")


def get_gemini_api_key() -> str:
    """API-ключ для Gemini (нужен, если OCR_ENGINE=gemini)"""
    return os.environ.get("GEMINI_API_KEY", "")


def get_zai_api_key() -> str:
    """API-ключ для Z.ai (нужен, если OCR_ENGINE=zai)"""
    return os.environ.get("ZAI_API_KEY", "")


def get_ocr_confidence_threshold() -> float:
    """Порог уверенности для локального OCR, ниже которого рекомендуется внешний."""
    return float(os.environ.get("OCR_CONFIDENCE_THRESHOLD", "0.5"))
