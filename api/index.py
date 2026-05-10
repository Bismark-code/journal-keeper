"""
FastAPI бэкенд для Приватного мультимодального дневника.
Упрощённая версия — только CRUD операции + SQLite.
OCR и редактор загружаются лениво.
"""

import os
import sys
import tempfile
from contextlib import contextmanager, asynccontextmanager
from pathlib import Path
from typing import Optional

sys.path.insert(0, "/home/z/my-project")

from fastapi import FastAPI, UploadFile, File, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from journal_keeper.db import (
    init_db, add_entry, search_by_tag, search_by_date,
    search_fts, get_recent, get_all_tags, delete_entries_by_date,
    get_all_raw_dumps, get_entry_by_id, update_entry_text,
    get_connection,
)

os.environ.setdefault("OCR_ENGINE", "tesseract")
os.environ.setdefault("DB_PATH", os.path.expanduser("~/.journal_keeper.db"))

# Инициализируем таблицы
init_db()


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[journal-api] Ready on port 3030", flush=True)
    yield
    print("[journal-api] Shutdown", flush=True)


app = FastAPI(title="Journal API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class EntryCreate(BaseModel):
    date: str
    time: Optional[str] = None
    topic: str = ""
    mood: str = ""
    text: str
    tags: list[str] = []

class EntryEdit(BaseModel):
    text: str


@app.get("/api/stats")
def get_stats():
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) as cnt FROM entries")
        total = c.fetchone()["cnt"]
        c.execute("SELECT COUNT(*) as cnt FROM tags")
        tags_count = c.fetchone()["cnt"]
        c.execute("SELECT date FROM entries ORDER BY date DESC LIMIT 1")
        row = c.fetchone()
    return {"total_entries": total, "total_tags": tags_count, "last_date": row["date"] if row else None}


@app.get("/api/entries")
def list_entries(limit: int = Query(20, ge=1, le=100)):
    with get_db() as conn:
        entries = get_recent(conn, limit)
    return {"entries": entries, "count": len(entries)}


@app.post("/api/entries")
def create_entry(entry: EntryCreate):
    try:
        raw = "\n".join([
            "===", f"ДАТА: {entry.date}",
            *(f"ВРЕМЯ: {entry.time}" for _ in [1] if entry.time),
            f"ТЕМА: {entry.topic}", f"ТЭГИ: {', '.join(entry.tags)}",
            f"НАСТРОЕНИЕ: {entry.mood}", f"ТЕКСТ: {entry.text}", "==="
        ])
        with get_db() as conn:
            eid = add_entry(conn, entry.date, entry.text,
                            time=entry.time, topic=entry.topic,
                            mood=entry.mood, tags=entry.tags, raw_dump=raw)
        return {"id": eid, "message": "Запись добавлена"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/entries/{entry_id}")
def get_entry(entry_id: int):
    with get_db() as conn:
        e = get_entry_by_id(conn, entry_id)
    if not e:
        raise HTTPException(status_code=404, detail="Не найдено")
    return e


@app.put("/api/entries/{entry_id}")
def edit_entry(entry_id: int, data: EntryEdit):
    with get_db() as conn:
        ok = update_entry_text(conn, entry_id, data.text)
    if not ok:
        raise HTTPException(status_code=404, detail="Не найдено")
    return {"message": "Обновлено"}


@app.delete("/api/entries/date/{date}")
def delete_by_date(date: str):
    with get_db() as conn:
        count = delete_entries_by_date(conn, date)
    return {"deleted": count}


@app.get("/api/search/tag")
def search_tag(tag: str = Query(...)):
    with get_db() as conn:
        entries = search_by_tag(conn, tag)
    return {"entries": entries, "count": len(entries)}


@app.get("/api/search/date")
def search_date(date: str = Query(...)):
    with get_db() as conn:
        entries = search_by_date(conn, date)
    return {"entries": entries, "count": len(entries)}


@app.get("/api/search/text")
def search_text(q: str = Query(...)):
    with get_db() as conn:
        entries = search_fts(conn, q)
    return {"entries": entries, "count": len(entries)}


@app.get("/api/tags")
def list_tags():
    with get_db() as conn:
        tags = get_all_tags(conn)
    return {"tags": tags}


@app.post("/api/edit")
def edit_text_api(data: EntryEdit):
    # Ленивый импорт — загружаем Ollama только при запросе
    from journal_keeper.editor import edit_text
    edited = edit_text(data.text)
    return {"original": data.text, "edited": edited}


@app.post("/api/ocr")
async def ocr_recognize(file: UploadFile = File(...), engine: Optional[str] = None):
    # Ленивый импорт — загружаем OCR только при запросе
    from journal_keeper.ocr import recognize_image
    suffix = Path(file.filename or "image.png").suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    try:
        text = recognize_image(tmp_path, engine=engine)
        return {"text": text, "filename": file.filename}
    finally:
        os.unlink(tmp_path)


@app.post("/api/import")
def import_archive(folder: str = Query(...)):
    from journal_keeper.importer import import_archive as do_import
    with get_db() as conn:
        stats = do_import(folder, conn=conn, verbose=False)
    return stats


@app.get("/api/export")
def export_entries():
    with get_db() as conn:
        dumps = get_all_raw_dumps(conn)
    return {"entries": dumps, "count": len(dumps)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3030)
