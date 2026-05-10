"""
Модуль работы с SQLite: создание таблиц, CRUD-операции, полнотекстовый поиск.
"""

import sqlite3
from datetime import datetime
from typing import Optional

from .config import get_db_path


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Возвращает соединение с БД с включёнными внешними ключами."""
    path = db_path or get_db_path()
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Создаёт таблицы и триггеры, если их нет. Возвращает соединение."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # Таблица записей
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            time TEXT,
            topic TEXT DEFAULT '',
            mood TEXT DEFAULT '',
            text TEXT NOT NULL,
            raw_dump TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    """)

    # Таблица тегов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    """)

    # Связующая таблица (многие-ко-многим) с каскадным удалением
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entry_tags (
            entry_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY (entry_id, tag_id),
            FOREIGN KEY (entry_id) REFERENCES entries(id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
        )
    """)

    # FTS5 виртуальная таблица для полнотекстового поиска
    # Используем trigram токенайзер для корректной работы с русским текстом
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
            text,
            topic,
            content='entries',
            content_rowid='id',
            tokenize='trigram'
        )
    """)

    # Триггеры для синхронизации FTS при вставке
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS entries_ai AFTER INSERT ON entries BEGIN
            INSERT INTO entries_fts(rowid, text, topic)
            VALUES (new.id, new.text, new.topic);
        END
    """)

    # Триггер для синхронизации FTS при удалении
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS entries_ad AFTER DELETE ON entries BEGIN
            INSERT INTO entries_fts(entries_fts, rowid, text, topic)
            VALUES ('delete', old.id, old.text, old.topic);
        END
    """)

    # Триггер для синхронизации FTS при обновлении
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS entries_au AFTER UPDATE ON entries BEGIN
            INSERT INTO entries_fts(entries_fts, rowid, text, topic)
            VALUES ('delete', old.id, old.text, old.topic);
            INSERT INTO entries_fts(rowid, text, topic)
            VALUES (new.id, new.text, new.topic);
        END
    """)

    conn.commit()
    return conn


def add_entry(
    conn: sqlite3.Connection,
    date: str,
    text: str,
    time: Optional[str] = None,
    topic: str = "",
    mood: str = "",
    tags: Optional[list[str]] = None,
    raw_dump: str = "",
) -> int:
    """
    Добавляет запись в БД и возвращает её id.
    Автоматически создаёт теги и связывает их с записью.
    """
    if not text.strip():
        raise ValueError("Текст записи не может быть пустым")

    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO entries (date, time, topic, mood, text, raw_dump)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (date, time, topic, mood, text, raw_dump),
    )
    entry_id = cursor.lastrowid

    # Добавляем теги
    if tags:
        for tag_name in tags:
            tag_name = tag_name.strip().lower()
            if not tag_name:
                continue
            # Вставляем тег, если его ещё нет
            cursor.execute(
                "INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag_name,)
            )
            cursor.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
            tag_row = cursor.fetchone()
            if tag_row:
                cursor.execute(
                    "INSERT OR IGNORE INTO entry_tags (entry_id, tag_id) VALUES (?, ?)",
                    (entry_id, tag_row["id"]),
                )

    conn.commit()
    return entry_id


def search_by_tag(conn: sqlite3.Connection, tag: str) -> list[dict]:
    """Поиск записей по тегу."""
    tag = tag.strip().lower()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT e.id, e.date, e.time, e.topic, e.mood, e.text, e.created_at
        FROM entries e
        JOIN entry_tags et ON e.id = et.entry_id
        JOIN tags t ON et.tag_id = t.id
        WHERE t.name = ?
        ORDER BY e.date DESC, e.time DESC
        """,
        (tag,),
    )
    return [dict(row) for row in cursor.fetchall()]


def search_by_date(conn: sqlite3.Connection, date: str) -> list[dict]:
    """Поиск записей по точной дате (ГГГГ-ММ-ДД)."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, date, time, topic, mood, text, created_at
        FROM entries
        WHERE date = ?
        ORDER BY time DESC
        """,
        (date,),
    )
    return [dict(row) for row in cursor.fetchall()]


def search_fts(conn: sqlite3.Connection, query: str) -> list[dict]:
    """Полнотекстовый поиск по text и topic через FTS5 (trigram)."""
    cursor = conn.cursor()
    # Для trigram токенайзера: ищем подстроку через * (минимум 3 символа)
    # Если запрос короче 3 символов — используем LIKE
    if len(query.strip()) < 3:
        cursor.execute(
            """
            SELECT id, date, time, topic, mood, text, created_at
            FROM entries
            WHERE text LIKE ? OR topic LIKE ?
            ORDER BY created_at DESC
            """,
            (f"%{query}%", f"%{query}%"),
        )
    else:
        # Trigram: MATCH ищет точное вхождение подстроки (3+ символа)
        safe_query = query.replace('"', '""')
        cursor.execute(
            """
            SELECT e.id, e.date, e.time, e.topic, e.mood, e.text, e.created_at
            FROM entries e
            JOIN entries_fts fts ON e.id = fts.rowid
            WHERE entries_fts MATCH ?
            ORDER BY rank
            """,
            (f'"{safe_query}"',),
        )
    return [dict(row) for row in cursor.fetchall()]


def get_recent(conn: sqlite3.Connection, n: int = 5) -> list[dict]:
    """Возвращает N последних записей по времени создания."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, date, time, topic, mood, text, created_at
        FROM entries
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (n,),
    )
    return [dict(row) for row in cursor.fetchall()]


def get_all_tags(conn: sqlite3.Connection) -> list[str]:
    """Возвращает список всех уникальных тегов."""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM tags ORDER BY name")
    return [row["name"] for row in cursor.fetchall()]


def delete_entries_by_date(conn: sqlite3.Connection, date: str) -> int:
    """Удаляет записи за указанную дату. Возвращает количество удалённых записей."""
    cursor = conn.cursor()
    # Сначала считаем
    cursor.execute("SELECT COUNT(*) as cnt FROM entries WHERE date = ?", (date,))
    count = cursor.fetchone()["cnt"]
    # Удаляем (каскад удалит связи с тегами)
    cursor.execute("DELETE FROM entries WHERE date = ?", (date,))
    conn.commit()
    # Очищаем неиспользуемые теги
    cursor.execute(
        """DELETE FROM tags WHERE id NOT IN (SELECT tag_id FROM entry_tags)"""
    )
    conn.commit()
    return count


def get_all_raw_dumps(conn: sqlite3.Connection) -> list[str]:
    """Возвращает все raw_dump для экспорта."""
    cursor = conn.cursor()
    cursor.execute("SELECT raw_dump FROM entries ORDER BY created_at ASC")
    return [row["raw_dump"] for row in cursor.fetchall() if row["raw_dump"]]


def entry_exists(conn: sqlite3.Connection, date: str, text_prefix: str) -> bool:
    """
    Проверяет существование записи по дате + первые 100 символов text.
    Используется для дедупликации при импорте.
    """
    cursor = conn.cursor()
    prefix = text_prefix[:100]
    cursor.execute(
        "SELECT COUNT(*) as cnt FROM entries WHERE date = ? AND SUBSTR(text, 1, 100) = ?",
        (date, prefix),
    )
    return cursor.fetchone()["cnt"] > 0


def get_entry_by_id(conn: sqlite3.Connection, entry_id: int) -> Optional[dict]:
    """Возвращает запись по id."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, date, time, topic, mood, text, raw_dump, created_at FROM entries WHERE id = ?",
        (entry_id,),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def update_entry_text(conn: sqlite3.Connection, entry_id: int, new_text: str) -> bool:
    """Обновляет текст записи по id. Возвращает True если обновлено."""
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE entries SET text = ? WHERE id = ?",
        (new_text, entry_id),
    )
    conn.commit()
    return cursor.rowcount > 0
