"""
FastAPI бэкенд для Приватного мультимодального дневника.
REST API, оборачивающий все модули journal_keeper.
"""

import os
import sys
import re
import io
import base64
import tempfile
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Добавляем родительскую директорию в path для импорта
sys.path.insert(0, str(Path(__file__).parent.parent))

from journal_keeper import db, parser, editor, ocr, importer
from journal_keeper.config import get_db_path, get_ollama_model, get_ocr_engine

# ─── Инициализация ─────────────────────────────────────────────────────────

app = FastAPI(
    title="Приватный мультимодальный дневник",
    description="REST API для дневника с OCR, LLM-редактором и полнотекстовым поиском",
    version="1.0.0",
)

# CORS — разрешаем запросы с фронтенда
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Глобальное соединение с БД
_conn = None


@app.on_event("startup")
def startup():
    global _conn
    _conn = db.init_db()


@app.on_event("shutdown")
def shutdown():
    global _conn
    if _conn:
        _conn.close()


# ─── Pydantic-модели ────────────────────────────────────────────────────────


class EntryCreate(BaseModel):
    date: str
    time: Optional[str] = None
    topic: str = ""
    mood: str = ""
    text: str
    tags: list[str] = []


class EntryUpdate(BaseModel):
    text: str


class SearchQuery(BaseModel):
    query: str
    type: str = "fts"  # fts | tag | date


class RawBlockCreate(BaseModel):
    raw_block: str


class OcrRequest(BaseModel):
    engine: str = "tesseract"


class EditRequest(BaseModel):
    text: str


class ImportRequest(BaseModel):
    folder_path: str


# ─── Эндпоинты ─────────────────────────────────────────────────────────────

# --- Записи ---


@app.get("/api/entries/recent")
def get_recent_entries(n: int = Query(20, ge=1, le=100)):
    """Последние N записей."""
    entries = db.get_recent(_conn, n)
    result = []
    for e in entries:
        tags = _tags_for(e["id"])
        result.append({**e, "tags": tags})
    return result


@app.get("/api/entries/{entry_id}")
def get_entry(entry_id: int):
    """Получить запись по ID."""
    entry = db.get_entry_by_id(_conn, entry_id)
    if not entry:
        raise HTTPException(404, "Запись не найдена")
    tags = _tags_for(entry_id)
    return {**entry, "tags": tags}


@app.post("/api/entries")
def create_entry(data: EntryCreate):
    """Добавить новую запись."""
    # Формируем raw_dump
    raw_lines = ["==="]
    raw_lines.append(f"ДАТА: {data.date}")
    if data.time:
        raw_lines.append(f"ВРЕМЯ: {data.time}")
    raw_lines.append(f"ТЕМА: {data.topic}")
    raw_lines.append(f"ТЭГИ: {', '.join(data.tags)}")
    raw_lines.append(f"НАСТРОЕНИЕ: {data.mood}")
    raw_lines.append(f"ТЕКСТ: {data.text}")
    raw_lines.append("===")
    raw_dump = "\n".join(raw_lines)

    try:
        entry_id = db.add_entry(
            conn=_conn,
            date=data.date,
            time=data.time,
            topic=data.topic,
            mood=data.mood,
            text=data.text,
            tags=data.tags,
            raw_dump=raw_dump,
        )
        return {"id": entry_id, "message": "Запись добавлена"}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/entries/parse-block")
def create_entry_from_block(data: RawBlockCreate):
    """Добавить запись из блока ===...===."""
    blocks = parser.extract_blocks_from_text(data.raw_block)
    if not blocks:
        raise HTTPException(400, "Блоки ===...=== не найдены")

    results = []
    for block in blocks:
        parsed = parser.parse_entry_block(block)
        if parsed is None:
            results.append({"status": "invalid", "error": "Пустой ТЕКСТ"})
            continue
        try:
            entry_id = db.add_entry(
                conn=_conn,
                date=parsed["date"],
                time=parsed["time"],
                topic=parsed["topic"],
                mood=parsed["mood"],
                text=parsed["text"],
                tags=parsed["tags"],
                raw_dump=parsed["raw_dump"],
            )
            results.append({"status": "added", "id": entry_id, "date": parsed["date"]})
        except ValueError as e:
            results.append({"status": "error", "error": str(e)})

    return {"results": results}


@app.put("/api/entries/{entry_id}")
def update_entry(entry_id: int, data: EntryUpdate):
    """Обновить текст записи."""
    ok = db.update_entry_text(_conn, entry_id, data.text)
    if not ok:
        raise HTTPException(404, "Запись не найдена")
    return {"message": "Запись обновлена"}


@app.delete("/api/entries/{entry_id}")
def delete_entry(entry_id: int):
    """Удалить запись по ID."""
    cursor = _conn.cursor()
    cursor.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
    _conn.commit()
    # Очистка неиспользуемых тегов
    cursor.execute("DELETE FROM tags WHERE id NOT IN (SELECT tag_id FROM entry_tags)")
    _conn.commit()
    if cursor.rowcount >= 0:
        return {"message": f"Запись #{entry_id} удалена"}
    raise HTTPException(404, "Запись не найдена")


@app.delete("/api/entries/by-date/{date_str}")
def delete_entries_by_date(date_str: str):
    """Удалить все записи за дату."""
    count = db.delete_entries_by_date(_conn, date_str)
    return {"message": f"Удалено {count} записей за {date_str}"}


# --- Поиск ---


@app.post("/api/search")
def search_entries(data: SearchQuery):
    """Поиск записей: полнотекстовый, по тегу, по дате."""
    if data.type == "tag":
        entries = db.search_by_tag(_conn, data.query)
    elif data.type == "date":
        entries = db.search_by_date(_conn, data.query)
    else:
        entries = db.search_fts(_conn, data.query)

    result = []
    for e in entries:
        tags = _tags_for(e["id"]) if "id" in e else []
        result.append({**e, "tags": tags})
    return result


# --- Тэги ---


@app.get("/api/tags")
def get_all_tags():
    """Все уникальные тэги с количеством записей."""
    tags = db.get_all_tags(_conn)
    result = []
    for tag in tags:
        entries = db.search_by_tag(_conn, tag)
        result.append({"name": tag, "count": len(entries)})
    return result


# --- OCR ---


@app.post("/api/ocr")
async def recognize_image(
    file: UploadFile = File(...),
    engine: str = Form("tesseract"),
):
    """Распознать текст с загруженного изображения."""
    # Сохраняем временный файл
    suffix = Path(file.filename or "image.png").suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        text = ocr.recognize_image(tmp_path, engine=engine)
        return {"text": text, "engine": engine}
    except Exception as e:
        raise HTTPException(500, f"OCR ошибка: {e}")
    finally:
        os.unlink(tmp_path)


# --- LLM-редактор ---


@app.post("/api/edit")
def edit_text(data: EditRequest):
    """Отредактировать текст через LLM."""
    edited = editor.edit_text(data.text)
    return {"original": data.text, "edited": edited}


# --- Импорт ---


@app.post("/api/import")
def import_archive(data: ImportRequest):
    """Импортировать архив из папки."""
    if not Path(data.folder_path).exists():
        raise HTTPException(400, f"Папка не найдена: {data.folder_path}")

    # Перехватываем stdout
    old_stdout = sys.stdout
    captured = io.StringIO()
    sys.stdout = captured

    try:
        stats = importer.import_archive(data.folder_path, conn=_conn, verbose=True)
    finally:
        sys.stdout = old_stdout

    log = captured.getvalue()
    return {"stats": stats, "log": log}


# --- Экспорт ---


@app.get("/api/export")
def export_entries():
    """Экспортировать все записи."""
    dumps = db.get_all_raw_dumps(_conn)
    content = "\n\n".join(dumps)
    return {"content": content, "count": len(dumps)}


# --- Информация ---


@app.get("/api/info")
def get_info():
    """Информация о конфигурации."""
    cursor = _conn.cursor()
    cursor.execute("SELECT COUNT(*) as cnt FROM entries")
    entry_count = cursor.fetchone()["cnt"]
    cursor.execute("SELECT COUNT(*) as cnt FROM tags")
    tag_count = cursor.fetchone()["cnt"]

    return {
        "version": "1.0.0",
        "db_path": get_db_path(),
        "ollama_model": get_ollama_model(),
        "ocr_engine": get_ocr_engine(),
        "entries_count": entry_count,
        "tags_count": tag_count,
    }


# ─── Вспомогательные функции ───────────────────────────────────────────────


def _tags_for(entry_id: int) -> list[str]:
    """Возвращает тэги для записи."""
    cursor = _conn.cursor()
    cursor.execute(
        """
        SELECT t.name FROM tags t
        JOIN entry_tags et ON t.id = et.tag_id
        WHERE et.entry_id = ?
        ORDER BY t.name
        """,
        (entry_id,),
    )
    return [row["name"] for row in cursor.fetchall()]


# ─── Запуск ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
