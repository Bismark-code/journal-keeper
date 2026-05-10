"""
Модуль импорта архива текстовых записей.
Рекурсивно находит .txt файлы, извлекает блоки ===...===,
проверяет уникальность и добавляет в БД.
"""

import sqlite3
from pathlib import Path
from typing import Optional

from .db import add_entry, entry_exists, init_db
from .parser import extract_blocks_from_text, parse_entry_block


def import_archive(
    folder_path: str,
    conn: Optional[sqlite3.Connection] = None,
    db_path: Optional[str] = None,
    verbose: bool = True,
) -> dict:
    """
    Импортирует архив записей из папки.

    Рекурсивно обходит все .txt файлы, извлекает блоки ===...===,
    проверяет уникальность (по дате + первые 100 символов text),
    и добавляет уникальные записи в БД.

    Параметры:
        folder_path: путь к папке с архивом
        conn: существующее соединение с БД (если None — создаётся новое)
        db_path: путь к БД (используется, если conn не передан)
        verbose: выводить ли прогресс в консоль

    Возвращает:
        Словарь со статистикой:
        {
            "files_found": int,     # найдено .txt файлов
            "blocks_found": int,    # найдено блоков
            "added": int,           # добавлено записей
            "duplicates": int,      # пропущено дубликатов
            "invalid": int,         # невалидных блоков
            "errors": list[str],    # ошибки чтения файлов
        }
    """
    folder = Path(folder_path)
    if not folder.exists():
        return {
            "files_found": 0,
            "blocks_found": 0,
            "added": 0,
            "duplicates": 0,
            "invalid": 0,
            "errors": [f"Папка не найдена: {folder_path}"],
        }

    if not folder.is_dir():
        return {
            "files_found": 0,
            "blocks_found": 0,
            "added": 0,
            "duplicates": 0,
            "invalid": 0,
            "errors": [f"Путь не является папкой: {folder_path}"],
        }

    own_conn = conn is None
    if own_conn:
        conn = init_db(db_path)

    stats = {
        "files_found": 0,
        "blocks_found": 0,
        "added": 0,
        "duplicates": 0,
        "invalid": 0,
        "errors": [],
    }

    try:
        # Рекурсивно ищем все .txt файлы
        txt_files = sorted(folder.rglob("*.txt"))
        stats["files_found"] = len(txt_files)

        if verbose:
            print(f"Найдено файлов: {len(txt_files)}")

        for txt_file in txt_files:
            try:
                content = txt_file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                try:
                    content = txt_file.read_text(encoding="cp1251")
                except Exception as e:
                    stats["errors"].append(
                        f"Не удалось прочитать {txt_file}: {type(e).__name__}: {e}"
                    )
                    continue
            except Exception as e:
                stats["errors"].append(
                    f"Не удалось прочитать {txt_file}: {type(e).__name__}: {e}"
                )
                continue

            # Извлекаем блоки
            blocks = extract_blocks_from_text(content)
            stats["blocks_found"] += len(blocks)

            for block in blocks:
                parsed = parse_entry_block(block)
                if parsed is None:
                    stats["invalid"] += 1
                    if verbose:
                        print(f"  [ПРОПУСК] Невалидный блок в {txt_file.name}")
                    continue

                # Проверяем уникальность
                if entry_exists(conn, parsed["date"], parsed["text"]):
                    stats["duplicates"] += 1
                    if verbose:
                        print(
                            f"  [ДУБЛИКАТ] Запись от {parsed['date']} уже существует"
                        )
                    continue

                # Добавляем
                try:
                    add_entry(
                        conn=conn,
                        date=parsed["date"],
                        time=parsed["time"],
                        topic=parsed["topic"],
                        mood=parsed["mood"],
                        text=parsed["text"],
                        tags=parsed["tags"],
                        raw_dump=parsed["raw_dump"],
                    )
                    stats["added"] += 1
                    if verbose:
                        print(f"  [+] Запись от {parsed['date']}: {parsed['topic'][:50]}")
                except Exception as e:
                    stats["errors"].append(
                        f"Ошибка добавления записи: {type(e).__name__}: {e}"
                    )

    finally:
        if own_conn:
            conn.close()

    if verbose:
        print(f"\nИтого: добавлено {stats['added']}, "
              f"дубликатов {stats['duplicates']}, "
              f"невалидных {stats['invalid']}")
        if stats["errors"]:
            print(f"Ошибки: {len(stats['errors'])}")

    return stats
