# Приватный мультимодальный дневник

Локальный дневник с LLM-редактором, OCR и полнотекстовым поиском. Все данные хранятся на вашем устройстве в SQLite — никакой облачной зависимости.

## Возможности

- **Записи дневника** — добавление, просмотр, редактирование, удаление записей в формате `===...===`
- **Полнотекстовый поиск** — FTS5 с trigram-токенайзером для корректной работы с русским текстом
- **Поиск по тэгам и датам** — гибкая система тегов (многие-ко-многим) с каскадным удалением
- **LLM-редактор** — улучшение текста записей через локальную модель Ollama (deepseek-r1:7b)
- **OCR** — распознавание рукописного текста с изображений (Tesseract / EasyOCR / Gemini / Z.ai)
- **Импорт архива** — массовый импорт из .txt файлов с дедупликацией
- **Экспорт** — выгрузка всех записей в текстовый файл
- **Три интерфейса**: CLI, GUI (tkinter), Web (Next.js + FastAPI)

## Установка

```bash
git clone https://github.com/YOUR_USERNAME/journal-keeper.git
cd journal-keeper

pip install -r journal_keeper/requirements.txt
```

### Зависимости OCR (опционально)

```bash
# Tesseract (системный пакет)
sudo apt install tesseract-ocr tesseract-ocr-rus

# EasyOCR (Python-пакет, может быть медленным при установке)
pip install easyocr
```

### LLM-редактор (опционально)

```bash
# Установите Ollama: https://ollama.com
ollama pull deepseek-r1:7b
```

## Использование

### CLI (интерактивный)

```bash
python -m journal_keeper
```

Доступные команды:
- `найди записи с тэгом X` — поиск по тегу
- `найди записи за ГГГГ-ММ-ДД` — поиск по дате
- `найди в тексте слово` — полнотекстовый поиск
- `последние N` — N последних записей
- `все тэги` — список уникальных тегов
- `экспорт` — экспорт всех записей
- `удали запись от ГГГГ-ММ-ДД` — удалить за дату
- `отредактируй: ТЕКСТ` — редактирование через LLM
- `распознай путь/к/изображению` — OCR рукописного текста
- `загрузить архив путь/к/папке` — импорт архива

### GUI (tkinter)

```bash
python -m journal_keeper --gui
```

### Web (FastAPI + Next.js)

```bash
# Запуск API-сервера
cd api
pip install fastapi uvicorn
python index.py  # Запускается на порту 3030

# Запуск фронтенда (требует Next.js проект)
# См. директорию web/
```

## Формат записи

```
===
ДАТА: 2026-05-10
ВРЕМЯ: 14:30
ТЕМА: Мои мысли
ТЭГИ: личное, дневник, размышления
НАСТРОЕНИЕ: спокойное
ТЕКСТ:
Сегодня хороший день. Солнце светит в окно,
и я решил записать свои мысли...
===
```

## Конфигурация (переменные окружения)

| Переменная | По умолчанию | Описание |
|---|---|---|
| `DB_PATH` | `~/.journal_keeper.db` | Путь к файлу SQLite |
| `OLLAMA_MODEL` | `deepseek-r1:7b` | Модель Ollama для редактора |
| `OCR_ENGINE` | `tesseract` | Движок OCR: tesseract, easyocr, gemini, zai |
| `OCR_CONFIDENCE_THRESHOLD` | `0.5` | Порог уверенности для локального OCR |
| `GEMINI_API_KEY` | — | API-ключ Google Gemini (для OCR) |
| `ZAI_API_KEY` | — | API-ключ Z.ai (для OCR) |

## Структура проекта

```
journal_keeper/
├── __init__.py      # Пакет, версия
├── __main__.py      # Точка входа (CLI / GUI)
├── config.py        # Конфигурация через env
├── db.py            # SQLite + FTS5
├── parser.py        # Парсер блоков ===...===
├── editor.py        # LLM-редактор (Ollama)
├── ocr.py           # OCR (4 движка)
├── importer.py      # Импорт архива
├── cli.py           # Интерактивный CLI
├── gui.py           # GUI на tkinter
└── requirements.txt # Зависимости

api/
└── index.py         # FastAPI REST API (порт 3030)

web/
├── page.tsx         # Next.js фронтенд
├── layout.tsx       # Layout с шрифтами
└── api-proxy-route.ts  # Прокси к FastAPI
```

## Технологии

- **Python 3.12+**
- **SQLite** с FTS5 (trigram)
- **Ollama** (deepseek-r1:7b)
- **Tesseract OCR** / EasyOCR / Gemini API / Z.ai API
- **tkinter** — десктопный GUI
- **FastAPI** — REST API
- **Next.js 16** + **shadcn/ui** — веб-интерфейс

## Лицензия

MIT
