"""
Интерактивный CLI для дневника.
Цикл while True с распознаванием команд по ключевым фразам.
"""

import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from . import db, editor, importer, ocr, parser
from .config import get_db_path


def format_entry(entry: dict, index: int = 0) -> str:
    """Форматирует запись для вывода в консоль."""
    lines = []
    lines.append(f"{'─' * 60}")
    lines.append(f"  #{entry.get('id', '?')}  |  {entry.get('date', '?')}")
    if entry.get("time"):
        lines.append(f"  Время: {entry['time']}")
    if entry.get("topic"):
        lines.append(f"  Тема: {entry['topic']}")
    if entry.get("mood"):
        lines.append(f"  Настроение: {entry['mood']}")
    lines.append(f"")
    # Выводим текст с отступом
    for line in entry.get("text", "").splitlines():
        lines.append(f"  {line}")
    lines.append(f"{'─' * 60}")
    return "\n".join(lines)


def print_help():
    """Выводит справку по командам."""
    help_text = """
╔══════════════════════════════════════════════════════════════╗
║              ПРИВАТНЫЙ МУЛЬТИМОДАЛЬНЫЙ ДНЕВНИК              ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Команды:                                                    ║
║                                                              ║
║  найди записи с тэгом X            — поиск по тегу           ║
║  найди записи за ГГГГ-ММ-ДД        — поиск по дате          ║
║  найди в тексте слово              — полнотекстовый поиск    ║
║  последние N                       — N последних записей     ║
║  все тэги                          — список уникальных тегов ║
║  экспорт                           — экспорт всех записей    ║
║  удали запись от ГГГГ-ММ-ДД        — удалить за дату        ║
║  отредактируй: ТЕКСТ               — редактирование через LLM║
║  перепиши: ТЕКСТ                   — то же, что отредактируй ║
║  распознай путь/к/изображению      — OCR рукописного текста  ║
║  загрузить архив путь/к/папке      — импорт архива записей   ║
║  help                              — эта справка             ║
║  quit / выход                      — завершить работу        ║
║                                                              ║
║  Ввод текста, начинающегося с === — добавить запись          ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(help_text)


def print_welcome():
    """Выводит приветственное сообщение."""
    print("\n" + "=" * 62)
    print("  ПРИВАТНЫЙ МУЛЬТИМОДАЛЬНЫЙ ДНЕВНИК v1.0")
    print("  Локальное хранение | LLM-редактор | OCR")
    print("=" * 62)
    print(f"  База данных: {get_db_path()}")
    print("  Введите 'help' для справки или начните вводить запись.")
    print()


def _ask_yes_no(prompt: str, default: bool = True) -> bool:
    """Спрашивает да/нет."""
    suffix = " [Д/н]: " if default else " [д/Н]: "
    answer = input(prompt + suffix).strip().lower()
    if not answer:
        return default
    return answer in ("д", "да", "y", "yes", "1")


def _ask_input(prompt: str, default: str = "") -> str:
    """Спрашивает ввод с значением по умолчанию."""
    if default:
        answer = input(f"{prompt} [{default}]: ").strip()
        return answer if answer else default
    return input(f"{prompt}: ").strip()


def _collect_entry_metadata(default_date: str = "") -> dict:
    """Собирает метаданные записи у пользователя."""
    entry_date = _ask_input("Дата (ГГГГ-ММ-ДД)", default_date or date.today().isoformat())
    entry_time = _ask_input("Время (ЧЧ:ММ, Enter — без времени)", "")
    entry_topic = _ask_input("Тема", "")
    entry_tags = _ask_input("Тэги (через запятую)", "")
    entry_mood = _ask_input("Настроение", "")

    tags_list = []
    if entry_tags:
        tags_list = [t.strip().lower() for t in re.split(r"[,;，；\s]+", entry_tags) if t.strip()]

    return {
        "date": entry_date,
        "time": entry_time if entry_time else None,
        "topic": entry_topic,
        "mood": entry_mood,
        "tags": tags_list,
    }


def _build_raw_block(meta: dict, text: str) -> str:
    """Формирует блок ===...=== из метаданных и текста."""
    lines = ["==="]
    lines.append(f"ДАТА: {meta['date']}")
    if meta.get("time"):
        lines.append(f"ВРЕМЯ: {meta['time']}")
    lines.append(f"ТЕМА: {meta.get('topic', '')}")
    lines.append(f"ТЭГИ: {', '.join(meta.get('tags', []))}")
    lines.append(f"НАСТРОЕНИЕ: {meta.get('mood', '')}")
    lines.append(f"ТЕКСТ: {text}")
    lines.append("===")
    return "\n".join(lines)


def handle_ocr(conn, image_path: str):
    """Обрабатывает команду распознавания изображения."""
    print(f"Распознаю текст с изображения: {image_path}")
    print("(Это может занять некоторое время...)\n")

    recognized_text = ocr.recognize_image(image_path)

    if not recognized_text:
        print("Текст не распознан или изображение не содержит рукописного текста.")
        return

    print("Распознанный текст:")
    print("─" * 40)
    print(recognized_text)
    print("─" * 40)

    if _ask_yes_no("Сохранить как запись?"):
        meta = _collect_entry_metadata()
        raw_block = _build_raw_block(meta, recognized_text)

        try:
            entry_id = db.add_entry(
                conn=conn,
                date=meta["date"],
                time=meta["time"],
                topic=meta["topic"],
                mood=meta["mood"],
                text=recognized_text,
                tags=meta["tags"],
                raw_dump=raw_block,
            )
            print(f"Запись сохранена (id={entry_id})")
        except ValueError as e:
            print(f"[ОШИБКА] {e}")
    else:
        print("Текст не сохранён.")


def handle_edit(text: str):
    """Обрабатывает команду редактирования текста."""
    print("Отправляю текст в LLM для редактирования...")
    print("(Это может занять некоторое время...)\n")

    edited = editor.edit_text(text)

    print("РЕЗУЛЬТАТ РЕДАКТИРОВАНИЯ:")
    print("─" * 40)
    print(edited)
    print("─" * 40)


def handle_export(conn):
    """Обрабатывает команду экспорта."""
    dumps = db.get_all_raw_dumps(conn)
    if not dumps:
        print("Нет записей для экспорта.")
        return

    filename = _ask_input("Имя файла для экспорта", "journal_export.txt")
    filepath = Path(filename)

    # Если указан только имя — сохраняем в текущую директорию
    if not filepath.is_absolute():
        filepath = Path.cwd() / filepath

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            for dump in dumps:
                f.write(dump + "\n\n")
        print(f"Экспортировано {len(dumps)} записей в {filepath}")
    except Exception as e:
        print(f"[ОШИБКА] Не удалось сохранить файл: {e}")


def handle_multiline_entry(conn, first_line: str):
    """
    Обрабатывает ввод записи, начинающейся с ===.
    Собирает многострочный ввод до закрытого ===.
    """
    lines = [first_line]

    # Если первая строка уже содержит закрытие ===
    if re.match(r"^===+\s*$", first_line.strip()) and len(lines) > 1:
        pass
    else:
        print("Вводите запись (завершите строкой ===):")
        while True:
            try:
                line = input()
                lines.append(line)
                if re.match(r"^===+\s*$", line.strip()):
                    break
            except EOFError:
                break

    full_block = "\n".join(lines)
    parsed = parser.parse_entry_block(full_block)

    if parsed is None:
        print("[ОШИБКА] Невалидная запись: отсутствует или пуст ТЕКСТ.")
        return

    try:
        entry_id = db.add_entry(
            conn=conn,
            date=parsed["date"],
            time=parsed["time"],
            topic=parsed["topic"],
            mood=parsed["mood"],
            text=parsed["text"],
            tags=parsed["tags"],
            raw_dump=parsed["raw_dump"],
        )
        print(f"Запись добавлена (id={entry_id}, дата: {parsed['date']})")
    except ValueError as e:
        print(f"[ОШИБКА] {e}")


def parse_command(user_input: str, conn) -> bool:
    """
    Распознаёт и обрабатывает команду.
    Возвращает True если следует продолжить цикл, False — выход.
    """
    inp = user_input.strip()
    inp_lower = inp.lower()

    # Выход
    if inp_lower in ("quit", "exit", "выход", "q"):
        print("До свидания!")
        return False

    # Справка
    if inp_lower == "help":
        print_help()
        return True

    # Поиск по тегу: "найди записи с тэгом X" или "найди записи с тегом X"
    m = re.match(
        r"(?i)найди\s+записи\s+с\s+те?э?гом\s+(.+)", inp
    )
    if m:
        tag = m.group(1).strip()
        entries = db.search_by_tag(conn, tag)
        if entries:
            print(f"\nНайдено записей с тэгом «{tag}»: {len(entries)}\n")
            for i, entry in enumerate(entries, 1):
                print(format_entry(entry, i))
        else:
            print(f"Записей с тэгом «{tag}» не найдено.")
        return True

    # Поиск по дате: "найди записи за ГГГГ-ММ-ДД"
    m = re.match(
        r"(?i)найди\s+записи\s+за\s+(\d{4}-\d{2}-\d{2})", inp
    )
    if m:
        search_date = m.group(1)
        entries = db.search_by_date(conn, search_date)
        if entries:
            print(f"\nЗаписи за {search_date}: {len(entries)}\n")
            for i, entry in enumerate(entries, 1):
                print(format_entry(entry, i))
        else:
            print(f"Записей за {search_date} не найдено.")
        return True

    # Полнотекстовый поиск: "найди в тексте слово"
    m = re.match(
        r"(?i)найди\s+в\s+тексте\s+(.+)", inp
    )
    if m:
        query = m.group(1).strip()
        entries = db.search_fts(conn, query)
        if entries:
            print(f"\nНайдено по запросу «{query}»: {len(entries)}\n")
            for i, entry in enumerate(entries, 1):
                print(format_entry(entry, i))
        else:
            print(f"По запросу «{query}» ничего не найдено.")
        return True

    # Последние N записей
    m = re.match(r"(?i)последние\s+(\d+)", inp)
    if m:
        n = int(m.group(1))
        entries = db.get_recent(conn, n)
        if entries:
            print(f"\nПоследние {n} записей:\n")
            for i, entry in enumerate(entries, 1):
                print(format_entry(entry, i))
        else:
            print("Записей пока нет.")
        return True

    # Все тэги
    if inp_lower in ("все тэги", "все теги", "все теги", "список тэгов", "список тегов"):
        tags = db.get_all_tags(conn)
        if tags:
            print(f"\nТэги ({len(tags)}): {', '.join(tags)}\n")
        else:
            print("Тэгов пока нет.")
        return True

    # Экспорт
    if inp_lower == "экспорт":
        handle_export(conn)
        return True

    # Удаление: "удали запись от ГГГГ-ММ-ДД"
    m = re.match(
        r"(?i)удали\s+запись\s+от\s+(\d{4}-\d{2}-\d{2})", inp
    )
    if m:
        del_date = m.group(1)
        entries = db.search_by_date(conn, del_date)
        if not entries:
            print(f"Записей за {del_date} не найдено.")
            return True

        print(f"Найдено {len(entries)} записей за {del_date}:")
        for i, entry in enumerate(entries, 1):
            print(format_entry(entry, i))

        if _ask_yes_no(f"Удалить все записи за {del_date}?", default=False):
            count = db.delete_entries_by_date(conn, del_date)
            print(f"Удалено записей: {count}")
        else:
            print("Отмена удаления.")
        return True

    # Редактирование: "отредактируй: ТЕКСТ" или "перепиши: ТЕКСТ"
    m = re.match(
        r"(?i)(отредактируй|перепиши)\s*[:：]\s*(.+)", inp, re.DOTALL
    )
    if m:
        text_to_edit = m.group(2).strip()
        handle_edit(text_to_edit)
        return True

    # OCR: "распознай путь/к/изображению"
    m = re.match(
        r"(?i)распознай\s+(.+)", inp
    )
    if m:
        image_path = m.group(1).strip()
        handle_ocr(conn, image_path)
        return True

    # Импорт архива: "загрузить архив путь/к/папке"
    m = re.match(
        r"(?i)загрузить\s+архив\s+(.+)", inp
    )
    if m:
        folder = m.group(1).strip()
        importer.import_archive(folder, conn=conn, verbose=True)
        return True

    # Ввод записи начинающейся с ===
    if inp.startswith("==="):
        handle_multiline_entry(conn, inp)
        return True

    # Неизвестная команда
    print("Неизвестная команда. Введите 'help' для справки.")
    return True


def run(db_path: Optional[str] = None):
    """Запускает интерактивный CLI дневника."""
    # Инициализируем БД
    conn = db.init_db(db_path)
    print_welcome()

    try:
        while True:
            try:
                user_input = input("📓> ")
            except EOFError:
                print("\nДо свидания!")
                break
            except KeyboardInterrupt:
                print("\nДо свидания!")
                break

            if not user_input.strip():
                continue

            should_continue = parse_command(user_input, conn)
            if not should_continue:
                break

    finally:
        conn.close()
