"""
Графическая оболочка для Приватного мультимодального дневника.
Построена на tkinter/ttk — не требует дополнительных зависимостей.

Все функции CLI продублированы в GUI:
- Просмотр, добавление, редактирование, удаление записей
- Поиск по тегу, дате, полнотекстовый
- OCR распознавание изображений
- LLM-редактирование текста
- Импорт архива и экспорт записей
"""

import os
import re
import threading
import tkinter as tk
from datetime import date, datetime
from pathlib import Path
from tkinter import (
    colorchooser,
    filedialog,
    messagebox,
    ttk,
)
from typing import Optional

from . import db, editor, importer, ocr, parser
from .config import get_db_path, get_ocr_engine, get_ollama_model


# ─── Утилиты ───────────────────────────────────────────────────────────────────

def _tags_for_entry(conn, entry_id: int) -> list[str]:
    """Возвращает список тегов для записи по entry_id."""
    cursor = conn.cursor()
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


def _format_entry_card(entry: dict, tags: list[str] | None = None) -> str:
    """Форматирует запись для текстового виджета."""
    lines = []
    lines.append(f"Дата: {entry.get('date', '?')}")
    if entry.get("time"):
        lines.append(f"Время: {entry['time']}")
    if entry.get("topic"):
        lines.append(f"Тема: {entry['topic']}")
    if entry.get("mood"):
        lines.append(f"Настроение: {entry['mood']}")
    if tags is not None:
        lines.append(f"Тэги: {', '.join(tags) if tags else '—'}")
    else:
        lines.append(f"Тэги: —")
    lines.append("")
    lines.append(entry.get("text", ""))
    return "\n".join(lines)


# ─── Основной класс приложения ─────────────────────────────────────────────────

class JournalApp:
    """Главное окно приложения «Приватный мультимодальный дневник»."""

    # Цветовая палитра (тёмная тема)
    BG = "#1e1e2e"
    BG_SIDE = "#181825"
    BG_CARD = "#313244"
    BG_INPUT = "#45475a"
    FG = "#cdd6f4"
    FG_DIM = "#a6adc8"
    FG_ACCENT = "#89b4fa"
    FG_GREEN = "#a6e3a1"
    FG_RED = "#f38ba8"
    FG_YELLOW = "#f9e2af"
    FG_ORANGE = "#fab387"

    def __init__(self, root: tk.Tk, db_path: Optional[str] = None):
        self.root = root
        self.root.title("Приватный мультимодальный дневник")
        self.root.geometry("1100x720")
        self.root.minsize(900, 600)
        self.root.configure(bg=self.BG)

        # База данных
        self._db_path = db_path or get_db_path()
        self.conn = db.init_db(self._db_path)

        # Текущее состояние
        self._current_entries: list[dict] = []
        self._selected_entry_id: Optional[int] = None
        self._busy = False  # флаг фоновой задачи

        # Строим интерфейс
        self._build_styles()
        self._build_sidebar()
        self._build_main_area()
        self._build_statusbar()

        # Показать последние записи
        self._show_recent()

        # Обработка закрытия
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ─── Стили ─────────────────────────────────────────────────────────────

    def _build_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("Sidebar.TFrame", background=self.BG_SIDE)
        style.configure("Main.TFrame", background=self.BG)
        style.configure(
            "Sidebar.TButton",
            background=self.BG_CARD,
            foreground=self.FG,
            font=("Segoe UI", 11),
            padding=(14, 10),
            anchor="w",
            relief="flat",
        )
        style.map(
            "Sidebar.TButton",
            background=[("active", self.BG_INPUT), ("pressed", self.FG_ACCENT)],
            foreground=[("active", self.FG_ACCENT)],
        )
        style.configure(
            "Accent.TButton",
            background=self.FG_ACCENT,
            foreground=self.BG,
            font=("Segoe UI", 11, "bold"),
            padding=(16, 8),
        )
        style.map(
            "Accent.TButton",
            background=[("active", "#74c7ec"), ("pressed", "#89dceb")],
        )
        style.configure(
            "Danger.TButton",
            background=self.FG_RED,
            foreground=self.BG,
            font=("Segoe UI", 11, "bold"),
            padding=(16, 8),
        )
        style.map(
            "Danger.TButton",
            background=[("active", "#eba0ac")],
        )
        style.configure(
            "Small.TButton",
            background=self.BG_CARD,
            foreground=self.FG,
            font=("Segoe UI", 10),
            padding=(10, 4),
        )
        style.map(
            "Small.TButton",
            background=[("active", self.BG_INPUT)],
            foreground=[("active", self.FG_ACCENT)],
        )
        style.configure("Card.TFrame", background=self.BG_CARD)
        style.configure(
            "Card.TLabel",
            background=self.BG_CARD,
            foreground=self.FG,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Title.TLabel",
            background=self.BG,
            foreground=self.FG_ACCENT,
            font=("Segoe UI", 14, "bold"),
        )
        style.configure(
            "Sub.TLabel",
            background=self.BG,
            foreground=self.FG_DIM,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Status.TLabel",
            background=self.BG_SIDE,
            foreground=self.FG_DIM,
            font=("Segoe UI", 9),
        )
        style.configure("TEntry", fieldbackground=self.BG_INPUT, foreground=self.FG)
        style.configure("TCombobox", fieldbackground=self.BG_INPUT, foreground=self.FG)

    # ─── Боковая панель ───────────────────────────────────────────────────

    def _build_sidebar(self):
        self.sidebar = ttk.Frame(self.root, style="Sidebar.TFrame", width=220)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)

        # Заголовок
        header = tk.Label(
            self.sidebar,
            text="Дневник",
            font=("Segoe UI", 16, "bold"),
            bg=self.BG_SIDE,
            fg=self.FG_ACCENT,
            anchor="w",
            padx=16,
            pady=(18, 4),
        )
        header.pack(fill=tk.X)

        version_label = tk.Label(
            self.sidebar,
            text="v1.0  |  Локальное хранение",
            font=("Segoe UI", 8),
            bg=self.BG_SIDE,
            fg=self.FG_DIM,
            anchor="w",
            padx=16,
        )
        version_label.pack(fill=tk.X, pady=(0, 16))

        # Кнопки навигации
        buttons = [
            ("Последние записи", self._show_recent),
            ("Добавить запись", self._show_add_entry),
            ("Поиск", self._show_search),
            ("Все тэги", self._show_tags),
            ("OCR распознавание", self._show_ocr),
            ("LLM-редактор", self._show_editor),
            ("Импорт архива", self._show_import),
            ("Экспорт записей", self._handle_export),
        ]
        for text, cmd in buttons:
            btn = ttk.Button(
                self.sidebar,
                text=text,
                style="Sidebar.TButton",
                command=cmd,
            )
            btn.pack(fill=tk.X, padx=10, pady=2)

        # Отступ
        tk.Frame(self.sidebar, bg=self.BG_SIDE, height=20).pack()

        # Инфо о БД
        db_label = tk.Label(
            self.sidebar,
            text=f"БД: {Path(self._db_path).name}",
            font=("Segoe UI", 8),
            bg=self.BG_SIDE,
            fg=self.FG_DIM,
            anchor="w",
            padx=16,
        )
        db_label.pack(fill=tk.X, side=tk.BOTTOM, pady=(0, 8))

        model_label = tk.Label(
            self.sidebar,
            text=f"LLM: {get_ollama_model()}",
            font=("Segoe UI", 8),
            bg=self.BG_SIDE,
            fg=self.FG_DIM,
            anchor="w",
            padx=16,
        )
        model_label.pack(fill=tk.X, side=tk.BOTTOM)

        ocr_label = tk.Label(
            self.sidebar,
            text=f"OCR: {get_ocr_engine()}",
            font=("Segoe UI", 8),
            bg=self.BG_SIDE,
            fg=self.FG_DIM,
            anchor="w",
            padx=16,
        )
        ocr_label.pack(fill=tk.X, side=tk.BOTTOM)

    # ─── Основная область ─────────────────────────────────────────────────

    def _build_main_area(self):
        self.main = ttk.Frame(self.root, style="Main.TFrame")
        self.main.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Заголовок страницы
        self.page_title = ttk.Label(
            self.main, text="Последние записи", style="Title.TLabel"
        )
        self.page_title.pack(anchor="w", padx=24, pady=(18, 0))

        self.page_subtitle = ttk.Label(
            self.main, text="", style="Sub.TLabel"
        )
        self.page_subtitle.pack(anchor="w", padx=24, pady=(2, 8))

        # Контейнер с прокруткой для содержимого
        self.content_canvas = tk.Canvas(self.main, bg=self.BG, highlightthickness=0)
        self.content_scrollbar = ttk.Scrollbar(
            self.main, orient="vertical", command=self.content_canvas.yview
        )
        self.content_frame = ttk.Frame(self.content_canvas, style="Main.TFrame")

        self.content_frame.bind(
            "<Configure>",
            lambda e: self.content_canvas.configure(
                scrollregion=self.content_canvas.bbox("all")
            ),
        )
        self.content_canvas.create_window(
            (0, 0), window=self.content_frame, anchor="nw"
        )
        self.content_canvas.configure(yscrollcommand=self.content_scrollbar.set)

        self.content_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.content_canvas.pack(fill=tk.BOTH, expand=True, padx=8)

        # Прокрутка колёсиком мыши
        self.content_canvas.bind_all(
            "<MouseWheel>",
            lambda e: self.content_canvas.yview_scroll(-1 * (e.delta // 120), "units"),
        )

        # Текущий вид
        self._current_view = None

    # ─── Строка состояния ─────────────────────────────────────────────────

    def _build_statusbar(self):
        self.statusbar = tk.Label(
            self.root,
            text="Готово",
            font=("Segoe UI", 9),
            bg=self.BG_SIDE,
            fg=self.FG_DIM,
            anchor="w",
            padx=12,
            pady=4,
        )
        self.statusbar.pack(side=tk.BOTTOM, fill=tk.X)

    def _set_status(self, text: str, color: str | None = None):
        self.statusbar.configure(text=text, fg=color or self.FG_DIM)

    # ─── Очистка контента ─────────────────────────────────────────────────

    def _clear_content(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        self._current_entries = []
        self._selected_entry_id = None

    # ─── Создание виджетов-помощников ──────────────────────────────────────

    def _make_labeled_entry(
        self, parent, label: str, default: str = "", width: int = 40
    ) -> tuple[ttk.Label, ttk.Entry]:
        """Создаёт пару «метка + поле ввода»."""
        frame = ttk.Frame(parent, style="Main.TFrame")
        frame.pack(fill=tk.X, padx=8, pady=4)

        lbl = tk.Label(
            frame,
            text=label,
            font=("Segoe UI", 10),
            bg=self.BG,
            fg=self.FG_DIM,
            width=14,
            anchor="w",
        )
        lbl.pack(side=tk.LEFT)

        var = tk.StringVar(value=default)
        entry = ttk.Entry(frame, textvariable=var, width=width, font=("Segoe UI", 10))
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        return lbl, entry

    def _make_text_area(
        self, parent, label: str, height: int = 8, initial: str = ""
    ) -> tuple[tk.Label, tk.Text]:
        """Создаёт пару «метка + многострочное текстовое поле»."""
        if label:
            lbl = tk.Label(
                parent,
                text=label,
                font=("Segoe UI", 10),
                bg=self.BG,
                fg=self.FG_DIM,
                anchor="w",
            )
            lbl.pack(fill=tk.X, padx=8, pady=(8, 2))

        text = tk.Text(
            parent,
            height=height,
            bg=self.BG_INPUT,
            fg=self.FG,
            font=("Segoe UI", 11),
            relief="flat",
            wrap="word",
            insertbackground=self.FG,
            padx=10,
            pady=8,
        )
        text.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        if initial:
            text.insert("1.0", initial)

        return lbl if label else None, text

    def _make_button_row(self, parent, buttons: list[tuple[str, callable, str]]):
        """Создаёт ряд кнопок. buttons: [(text, command, style), ...]"""
        frame = ttk.Frame(parent, style="Main.TFrame")
        frame.pack(fill=tk.X, padx=8, pady=12)
        for text, cmd, style in buttons:
            ttk.Button(frame, text=text, style=style, command=cmd).pack(
                side=tk.LEFT, padx=4
            )
        return frame

    # ═══════════════════════════════════════════════════════════════════════
    #   ВИДЫ (VIEWS)
    # ═══════════════════════════════════════════════════════════════════════

    # ─── Последние записи ─────────────────────────────────────────────────

    def _show_recent(self):
        self._clear_content()
        self._current_view = "recent"
        self.page_title.configure(text="Последние записи")
        entries = db.get_recent(self.conn, 50)
        self.page_subtitle.configure(text=f"Показано {len(entries)} записей")
        self._render_entries_list(entries)
        self._set_status("Последние записи загружены")

    # ─── Список записей (рендеринг) ───────────────────────────────────────

    def _render_entries_list(self, entries: list[dict]):
        self._current_entries = entries
        if not entries:
            tk.Label(
                self.content_frame,
                text="Записей не найдено.",
                font=("Segoe UI", 12),
                bg=self.BG,
                fg=self.FG_DIM,
            ).pack(pady=40)
            return

        for i, entry in enumerate(entries):
            tags = _tags_for_entry(self.conn, entry["id"]) if "id" in entry else []
            card = self._make_entry_card(entry, tags, i)

    def _make_entry_card(self, entry: dict, tags: list[str], index: int):
        """Создаёт карточку записи."""
        card = tk.Frame(
            self.content_frame,
            bg=self.BG_CARD,
            padx=16,
            pady=12,
            cursor="hand2",
        )
        card.pack(fill=tk.X, padx=8, pady=4)

        # Заголовок карточки: дата + тема
        header_frame = tk.Frame(card, bg=self.BG_CARD)
        header_frame.pack(fill=tk.X)

        date_text = entry.get("date", "?")
        if entry.get("time"):
            date_text += f"  {entry['time']}"
        if entry.get("topic"):
            date_text += f"  —  {entry['topic']}"

        header_lbl = tk.Label(
            header_frame,
            text=date_text,
            font=("Segoe UI", 11, "bold"),
            bg=self.BG_CARD,
            fg=self.FG_ACCENT,
            anchor="w",
        )
        header_lbl.pack(side=tk.LEFT)

        # Настроение
        if entry.get("mood"):
            mood_lbl = tk.Label(
                header_frame,
                text=entry["mood"],
                font=("Segoe UI", 10),
                bg=self.BG_CARD,
                fg=self.FG_YELLOW,
                anchor="e",
            )
            mood_lbl.pack(side=tk.RIGHT)

        # Тэги
        if tags:
            tags_frame = tk.Frame(card, bg=self.BG_CARD)
            tags_frame.pack(fill=tk.X, pady=(4, 0))
            for tag in tags[:5]:
                tag_lbl = tk.Label(
                    tags_frame,
                    text=f" #{tag} ",
                    font=("Segoe UI", 9),
                    bg=self.BG_INPUT,
                    fg=self.FG_GREEN,
                    padx=4,
                    pady=1,
                )
                tag_lbl.pack(side=tk.LEFT, padx=2)
            if len(tags) > 5:
                more = tk.Label(
                    tags_frame,
                    text=f" +{len(tags) - 5}",
                    font=("Segoe UI", 9),
                    bg=self.BG_CARD,
                    fg=self.FG_DIM,
                )
                more.pack(side=tk.LEFT, padx=2)

        # Превью текста (первые 2 строки)
        text_preview = entry.get("text", "")
        preview_lines = text_preview.split("\n")[:2]
        preview = "\n".join(preview_lines)
        if len(preview) > 150:
            preview = preview[:150] + "…"

        preview_lbl = tk.Label(
            card,
            text=preview,
            font=("Segoe UI", 10),
            bg=self.BG_CARD,
            fg=self.FG,
            anchor="w",
            justify="left",
            wraplength=700,
        )
        preview_lbl.pack(fill=tk.X, pady=(6, 0))

        # Привязка клика — открытие записи
        entry_id = entry.get("id")
        for widget in [card, header_lbl, preview_lbl]:
            widget.bind("<Button-1>", lambda e, eid=entry_id: self._show_entry_detail(eid))
            widget.configure(cursor="hand2")

        # Кнопки на карточке
        btn_frame = tk.Frame(card, bg=self.BG_CARD)
        btn_frame.pack(fill=tk.X, pady=(8, 0))

        ttk.Button(
            btn_frame,
            text="Открыть",
            style="Small.TButton",
            command=lambda eid=entry_id: self._show_entry_detail(eid),
        ).pack(side=tk.LEFT, padx=2)

        ttk.Button(
            btn_frame,
            text="LLM-редакт.",
            style="Small.TButton",
            command=lambda eid=entry_id: self._edit_entry_with_llm(eid),
        ).pack(side=tk.LEFT, padx=2)

        ttk.Button(
            btn_frame,
            text="Удалить",
            style="Small.TButton",
            command=lambda eid=entry_id, dt=entry.get("date"): self._delete_entry(eid, dt),
        ).pack(side=tk.LEFT, padx=2)

    # ─── Детальный просмотр записи ────────────────────────────────────────

    def _show_entry_detail(self, entry_id: int):
        entry = db.get_entry_by_id(self.conn, entry_id)
        if not entry:
            messagebox.showwarning("Не найдено", f"Запись id={entry_id} не найдена.")
            return

        self._clear_content()
        self._selected_entry_id = entry_id
        self._current_view = "detail"

        tags = _tags_for_entry(self.conn, entry_id)

        self.page_title.configure(text=f"Запись #{entry_id}")
        self.page_subtitle.configure(
            text=f"{entry['date']}  |  {entry.get('topic', 'Без темы')}"
        )

        # Карточка с деталями
        card = tk.Frame(self.content_frame, bg=self.BG_CARD, padx=20, pady=16)
        card.pack(fill=tk.X, padx=8, pady=8)

        # Поля мета
        meta_frame = tk.Frame(card, bg=self.BG_CARD)
        meta_frame.pack(fill=tk.X)

        fields = []
        if entry.get("time"):
            fields.append(("Время:", entry["time"]))
        if entry.get("topic"):
            fields.append(("Тема:", entry["topic"]))
        if entry.get("mood"):
            fields.append(("Настроение:", entry["mood"]))
        fields.append(("Тэги:", ", ".join(tags) if tags else "—"))
        fields.append(("Создано:", entry.get("created_at", "—")))

        for label_text, value_text in fields:
            row = tk.Frame(meta_frame, bg=self.BG_CARD)
            row.pack(fill=tk.X, pady=1)
            tk.Label(
                row,
                text=label_text,
                font=("Segoe UI", 10, "bold"),
                bg=self.BG_CARD,
                fg=self.FG_DIM,
                width=14,
                anchor="w",
            ).pack(side=tk.LEFT)
            tk.Label(
                row,
                text=value_text,
                font=("Segoe UI", 10),
                bg=self.BG_CARD,
                fg=self.FG,
                anchor="w",
            ).pack(side=tk.LEFT)

        # Текст записи
        _, text_widget = self._make_text_area(
            self.content_frame, label="Текст записи:", height=15, initial=entry.get("text", "")
        )
        text_widget.configure(state="normal")  # разрешаем редактирование

        self._detail_text_widget = text_widget
        self._detail_entry = entry

        # Кнопки действий
        self._make_button_row(
            self.content_frame,
            [
                ("Сохранить изменения", self._save_entry_edit, "Accent.TButton"),
                ("LLM-редактирование", lambda: self._edit_entry_with_llm(entry_id), "Accent.TButton"),
                ("Удалить", lambda: self._delete_entry(entry_id, entry.get("date")), "Danger.TButton"),
                ("Назад", self._show_recent, "Small.TButton"),
            ],
        )

    def _save_entry_edit(self):
        """Сохраняет отредактированный текст текущей записи."""
        if not self._selected_entry_id:
            return
        new_text = self._detail_text_widget.get("1.0", tk.END).strip()
        if not new_text:
            messagebox.showwarning("Пусто", "Текст записи не может быть пустым.")
            return
        db.update_entry_text(self.conn, self._selected_entry_id, new_text)
        self._set_status(f"Запись #{self._selected_entry_id} сохранена", self.FG_GREEN)
        messagebox.showinfo("Сохранено", "Текст записи обновлён.")

    # ─── Добавление записи ────────────────────────────────────────────────

    def _show_add_entry(self):
        self._clear_content()
        self._current_view = "add"
        self.page_title.configure(text="Добавить запись")
        self.page_subtitle.configure(text="Заполните поля и сохраните")

        card = tk.Frame(self.content_frame, bg=self.BG_CARD, padx=16, pady=16)
        card.pack(fill=tk.X, padx=8, pady=8)

        _, self._add_date = self._make_labeled_entry(
            card, "Дата:", date.today().isoformat()
        )
        _, self._add_time = self._make_labeled_entry(card, "Время:", "")
        _, self._add_topic = self._make_labeled_entry(card, "Тема:", "")
        _, self._add_tags = self._make_labeled_entry(card, "Тэги (через запятую):", "")
        _, self._add_mood = self._make_labeled_entry(card, "Настроение:", "")

        _, self._add_text = self._make_text_area(
            self.content_frame, label="Текст записи:", height=12
        )

        # Альтернативный ввод: блок ===...===
        tk.Label(
            self.content_frame,
            text="Или вставьте блок в формате ===...=== :",
            font=("Segoe UI", 10),
            bg=self.BG,
            fg=self.FG_DIM,
            anchor="w",
        ).pack(fill=tk.X, padx=16, pady=(12, 2))

        _, self._add_raw_block = self._make_text_area(
            self.content_frame, label="", height=8
        )

        self._make_button_row(
            self.content_frame,
            [
                ("Сохранить", self._do_add_entry, "Accent.TButton"),
                ("Очистить", self._clear_add_form, "Small.TButton"),
                ("Назад", self._show_recent, "Small.TButton"),
            ],
        )

    def _do_add_entry(self):
        """Сохраняет новую запись из формы."""
        # Проверяем, был ли вставлен блок ===...===
        raw = self._add_raw_block.get("1.0", tk.END).strip()
        if raw.startswith("==="):
            blocks = parser.extract_blocks_from_text(raw)
            if blocks:
                parsed = parser.parse_entry_block(blocks[0])
                if parsed:
                    try:
                        entry_id = db.add_entry(
                            conn=self.conn,
                            date=parsed["date"],
                            time=parsed["time"],
                            topic=parsed["topic"],
                            mood=parsed["mood"],
                            text=parsed["text"],
                            tags=parsed["tags"],
                            raw_dump=parsed["raw_dump"],
                        )
                        self._set_status(
                            f"Запись добавлена (id={entry_id})", self.FG_GREEN
                        )
                        messagebox.showinfo("Готово", f"Запись добавлена (id={entry_id})")
                        self._show_recent()
                        return
                    except ValueError as e:
                        messagebox.showerror("Ошибка", str(e))
                        return
                else:
                    messagebox.showwarning(
                        "Ошибка парсинга",
                        "Блок ===...=== невалиден: отсутствует или пуст ТЕКСТ.",
                    )
                    return

        # Обычная форма
        entry_date = self._add_date.get().strip()
        entry_time = self._add_time.get().strip() or None
        entry_topic = self._add_topic.get().strip()
        entry_tags_str = self._add_tags.get().strip()
        entry_mood = self._add_mood.get().strip()
        entry_text = self._add_text.get("1.0", tk.END).strip()

        if not entry_text:
            messagebox.showwarning("Пусто", "Текст записи не может быть пустым.")
            return

        if not entry_date:
            entry_date = date.today().isoformat()

        tags_list = []
        if entry_tags_str:
            tags_list = [
                t.strip().lower()
                for t in re.split(r"[,;，；\s]+", entry_tags_str)
                if t.strip()
            ]

        # Формируем raw_dump
        raw_lines = ["==="]
        raw_lines.append(f"ДАТА: {entry_date}")
        if entry_time:
            raw_lines.append(f"ВРЕМЯ: {entry_time}")
        raw_lines.append(f"ТЕМА: {entry_topic}")
        raw_lines.append(f"ТЭГИ: {', '.join(tags_list)}")
        raw_lines.append(f"НАСТРОЕНИЕ: {entry_mood}")
        raw_lines.append(f"ТЕКСТ: {entry_text}")
        raw_lines.append("===")
        raw_dump = "\n".join(raw_lines)

        try:
            entry_id = db.add_entry(
                conn=self.conn,
                date=entry_date,
                time=entry_time,
                topic=entry_topic,
                mood=entry_mood,
                text=entry_text,
                tags=tags_list,
                raw_dump=raw_dump,
            )
            self._set_status(f"Запись добавлена (id={entry_id})", self.FG_GREEN)
            messagebox.showinfo("Готово", f"Запись добавлена (id={entry_id})")
            self._show_recent()
        except ValueError as e:
            messagebox.showerror("Ошибка", str(e))

    def _clear_add_form(self):
        self._add_date.delete(0, tk.END)
        self._add_date.insert(0, date.today().isoformat())
        self._add_time.delete(0, tk.END)
        self._add_topic.delete(0, tk.END)
        self._add_tags.delete(0, tk.END)
        self._add_mood.delete(0, tk.END)
        self._add_text.delete("1.0", tk.END)
        self._add_raw_block.delete("1.0", tk.END)

    # ─── Поиск ────────────────────────────────────────────────────────────

    def _show_search(self):
        self._clear_content()
        self._current_view = "search"
        self.page_title.configure(text="Поиск")
        self.page_subtitle.configure(text="Поиск по тегу, дате или полнотекстовый")

        # Панель поиска
        search_panel = tk.Frame(self.content_frame, bg=self.BG_CARD, padx=16, pady=12)
        search_panel.pack(fill=tk.X, padx=8, pady=8)

        # Тип поиска
        type_frame = tk.Frame(search_panel, bg=self.BG_CARD)
        type_frame.pack(fill=tk.X, pady=(0, 8))

        self._search_type = tk.StringVar(value="fts")
        for text, val in [
            ("Полнотекстовый", "fts"),
            ("По тэгу", "tag"),
            ("По дате", "date"),
        ]:
            tk.Radiobutton(
                type_frame,
                text=text,
                variable=self._search_type,
                value=val,
                bg=self.BG_CARD,
                fg=self.FG,
                selectcolor=self.BG_INPUT,
                font=("Segoe UI", 10),
                activebackground=self.BG_CARD,
                activeforeground=self.FG_ACCENT,
            ).pack(side=tk.LEFT, padx=8)

        # Поле ввода
        input_frame = tk.Frame(search_panel, bg=self.BG_CARD)
        input_frame.pack(fill=tk.X)

        self._search_query = tk.StringVar()
        search_entry = ttk.Entry(
            input_frame,
            textvariable=self._search_query,
            font=("Segoe UI", 12),
            width=50,
        )
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        ttk.Button(
            input_frame,
            text="Найти",
            style="Accent.TButton",
            command=self._do_search,
        ).pack(side=tk.LEFT)

        # Подсказка
        tk.Label(
            search_panel,
            text="Введите запрос и нажмите «Найти». Для поиска по дате укажите ГГГГ-ММ-ДД.",
            font=("Segoe UI", 9),
            bg=self.BG_CARD,
            fg=self.FG_DIM,
            anchor="w",
        ).pack(fill=tk.X, pady=(6, 0))

        # Область результатов
        self._search_results_frame = tk.Frame(self.content_frame, bg=self.BG)
        self._search_results_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Привязка Enter
        search_entry.bind("<Return>", lambda e: self._do_search())

    def _do_search(self):
        """Выполняет поиск и отображает результаты."""
        query = self._search_query.get().strip()
        if not query:
            messagebox.showwarning("Пусто", "Введите запрос для поиска.")
            return

        search_type = self._search_type.get()

        if search_type == "tag":
            entries = db.search_by_tag(self.conn, query)
            subtitle = f"Тэг: «{query}» — найдено {len(entries)}"
        elif search_type == "date":
            entries = db.search_by_date(self.conn, query)
            subtitle = f"Дата: {query} — найдено {len(entries)}"
        else:
            entries = db.search_fts(self.conn, query)
            subtitle = f"Запрос: «{query}» — найдено {len(entries)}"

        self.page_subtitle.configure(text=subtitle)

        # Очищаем результаты
        for w in self._search_results_frame.winfo_children():
            w.destroy()

        self._current_entries = entries
        if not entries:
            tk.Label(
                self._search_results_frame,
                text="Ничего не найдено.",
                font=("Segoe UI", 12),
                bg=self.BG,
                fg=self.FG_DIM,
            ).pack(pady=30)
            return

        # Рендерим карточки в области результатов
        for entry in entries:
            tags = _tags_for_entry(self.conn, entry["id"]) if "id" in entry else []
            card = tk.Frame(
                self._search_results_frame,
                bg=self.BG_CARD,
                padx=14,
                pady=10,
                cursor="hand2",
            )
            card.pack(fill=tk.X, pady=3)

            # Заголовок
            header = entry.get("date", "?")
            if entry.get("time"):
                header += f"  {entry['time']}"
            if entry.get("topic"):
                header += f"  —  {entry['topic']}"

            tk.Label(
                card,
                text=header,
                font=("Segoe UI", 10, "bold"),
                bg=self.BG_CARD,
                fg=self.FG_ACCENT,
                anchor="w",
            ).pack(fill=tk.X)

            # Тэги
            if tags:
                tags_str = "  ".join(f"#{t}" for t in tags[:5])
                tk.Label(
                    card,
                    text=tags_str,
                    font=("Segoe UI", 9),
                    bg=self.BG_CARD,
                    fg=self.FG_GREEN,
                    anchor="w",
                ).pack(fill=tk.X)

            # Превью
            preview = entry.get("text", "")[:120] + ("…" if len(entry.get("text", "")) > 120 else "")
            tk.Label(
                card,
                text=preview,
                font=("Segoe UI", 10),
                bg=self.BG_CARD,
                fg=self.FG,
                anchor="w",
                wraplength=650,
            ).pack(fill=tk.X, pady=(4, 0))

            # Клик
            eid = entry.get("id")
            for w in card.winfo_children():
                w.bind("<Button-1>", lambda e, eid=eid: self._show_entry_detail(eid))
            card.bind("<Button-1>", lambda e, eid=eid: self._show_entry_detail(eid))

        self._set_status(f"Поиск завершён: {len(entries)} записей")

    # ─── Все тэги ─────────────────────────────────────────────────────────

    def _show_tags(self):
        self._clear_content()
        self._current_view = "tags"
        self.page_title.configure(text="Все тэги")
        tags = db.get_all_tags(self.conn)
        self.page_subtitle.configure(text=f"Всего тегов: {len(tags)}")

        if not tags:
            tk.Label(
                self.content_frame,
                text="Тэгов пока нет.",
                font=("Segoe UI", 12),
                bg=self.BG,
                fg=self.FG_DIM,
            ).pack(pady=40)
            return

        # Сетка тегов
        tags_canvas = tk.Canvas(self.content_frame, bg=self.BG, highlightthickness=0)
        tags_inner = tk.Frame(tags_canvas, bg=self.BG)

        cols = 4
        for i, tag in enumerate(tags):
            row, col = divmod(i, cols)
            # Считаем количество записей с этим тегом
            entries = db.search_by_tag(self.conn, tag)
            count = len(entries)

            tag_frame = tk.Frame(tags_inner, bg=self.BG_CARD, padx=10, pady=8, cursor="hand2")
            tag_frame.grid(row=row, column=col, padx=6, pady=4, sticky="ew")

            tk.Label(
                tag_frame,
                text=f"#{tag}",
                font=("Segoe UI", 11, "bold"),
                bg=self.BG_CARD,
                fg=self.FG_GREEN,
                anchor="w",
            ).pack(side=tk.LEFT)

            tk.Label(
                tag_frame,
                text=f" ({count})",
                font=("Segoe UI", 9),
                bg=self.BG_CARD,
                fg=self.FG_DIM,
                anchor="w",
            ).pack(side=tk.LEFT)

            # Клик по тегу — поиск
            for w in [tag_frame] + tag_frame.winfo_children():
                w.bind(
                    "<Button-1>",
                    lambda e, t=tag: self._search_by_tag_click(t),
                )

        for c in range(cols):
            tags_inner.columnconfigure(c, weight=1)

        tags_canvas.create_window((0, 0), window=tags_inner, anchor="nw")
        tags_canvas.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        tags_inner.update_idletasks()
        tags_canvas.configure(scrollregion=tags_canvas.bbox("all"))

        self._set_status(f"Загружено {len(tags)} тегов")

    def _search_by_tag_click(self, tag: str):
        """Переход к результатам поиска по клику на тег."""
        self._show_search()
        self._search_type.set("tag")
        self._search_query.set(tag)
        self._do_search()

    # ─── OCR ──────────────────────────────────────────────────────────────

    def _show_ocr(self):
        self._clear_content()
        self._current_view = "ocr"
        self.page_title.configure(text="OCR — распознавание рукописного текста")
        self.page_subtitle.configure(text=f"Движок: {get_ocr_engine()}")

        card = tk.Frame(self.content_frame, bg=self.BG_CARD, padx=16, pady=16)
        card.pack(fill=tk.X, padx=8, pady=8)

        # Выбор файла
        file_frame = tk.Frame(card, bg=self.BG_CARD)
        file_frame.pack(fill=tk.X, pady=4)

        tk.Label(
            file_frame,
            text="Изображение:",
            font=("Segoe UI", 10),
            bg=self.BG_CARD,
            fg=self.FG_DIM,
            width=14,
            anchor="w",
        ).pack(side=tk.LEFT)

        self._ocr_path = tk.StringVar()
        ttk.Entry(
            file_frame, textvariable=self._ocr_path, font=("Segoe UI", 10)
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        ttk.Button(
            file_frame,
            text="Обзор…",
            style="Small.TButton",
            command=self._ocr_browse,
        ).pack(side=tk.LEFT)

        # Выбор движка
        engine_frame = tk.Frame(card, bg=self.BG_CARD)
        engine_frame.pack(fill=tk.X, pady=4)

        tk.Label(
            engine_frame,
            text="Движок OCR:",
            font=("Segoe UI", 10),
            bg=self.BG_CARD,
            fg=self.FG_DIM,
            width=14,
            anchor="w",
        ).pack(side=tk.LEFT)

        self._ocr_engine_var = tk.StringVar(value=get_ocr_engine())
        engine_combo = ttk.Combobox(
            engine_frame,
            textvariable=self._ocr_engine_var,
            values=["tesseract", "easyocr", "gemini", "zai"],
            state="readonly",
            width=15,
        )
        engine_combo.pack(side=tk.LEFT)

        # Кнопка распознавания
        self._make_button_row(
            self.content_frame,
            [
                ("Распознать", self._do_ocr, "Accent.TButton"),
                ("Распознать и сохранить", self._do_ocr_and_save, "Accent.TButton"),
            ],
        )

        # Результат
        tk.Label(
            self.content_frame,
            text="Результат распознавания:",
            font=("Segoe UI", 10),
            bg=self.BG,
            fg=self.FG_DIM,
            anchor="w",
        ).pack(fill=tk.X, padx=16, pady=(12, 2))

        _, self._ocr_result = self._make_text_area(
            self.content_frame, label="", height=10
        )

        self._set_status("Выберите изображение для распознавания")

    def _ocr_browse(self):
        path = filedialog.askopenfilename(
            title="Выберите изображение",
            filetypes=[
                ("Изображения", "*.jpg *.jpeg *.png *.bmp *.tiff *.webp"),
                ("Все файлы", "*.*"),
            ],
        )
        if path:
            self._ocr_path.set(path)

    def _do_ocr(self):
        """Запускает OCR в фоновом потоке."""
        image_path = self._ocr_path.get().strip()
        if not image_path:
            messagebox.showwarning("Не выбрано", "Укажите путь к изображению.")
            return

        if not Path(image_path).exists():
            messagebox.showerror("Не найдено", f"Файл не найден: {image_path}")
            return

        engine = self._ocr_engine_var.get()
        self._set_status("Распознаю текст… Это может занять время", self.FG_YELLOW)
        self._ocr_result.delete("1.0", tk.END)
        self._ocr_result.insert("1.0", "Распознаю текст… Подождите…")

        def _worker():
            try:
                text = ocr.recognize_image(image_path, engine=engine)
                self.root.after(0, self._ocr_done, text)
            except Exception as e:
                self.root.after(0, self._ocr_error, str(e))

        threading.Thread(target=_worker, daemon=True).start()

    def _ocr_done(self, text: str):
        self._ocr_result.delete("1.0", tk.END)
        self._ocr_result.insert("1.0", text or "(Текст не распознан)")
        self._set_status("Распознавание завершено", self.FG_GREEN)

    def _ocr_error(self, error: str):
        self._ocr_result.delete("1.0", tk.END)
        self._ocr_result.insert("1.0", f"Ошибка: {error}")
        self._set_status(f"Ошибка OCR: {error}", self.FG_RED)

    def _do_ocr_and_save(self):
        """Распознаёт и затем открывает форму добавления с результатом."""
        image_path = self._ocr_path.get().strip()
        if not image_path:
            messagebox.showwarning("Не выбрано", "Укажите путь к изображению.")
            return

        if not Path(image_path).exists():
            messagebox.showerror("Не найдено", f"Файл не найден: {image_path}")
            return

        engine = self._ocr_engine_var.get()
        self._set_status("Распознаю текст…", self.FG_YELLOW)

        def _worker():
            try:
                text = ocr.recognize_image(image_path, engine=engine)
                self.root.after(0, self._ocr_save_done, text, image_path)
            except Exception as e:
                self.root.after(0, self._ocr_error, str(e))

        threading.Thread(target=_worker, daemon=True).start()

    def _ocr_save_done(self, text: str, image_path: str):
        if not text:
            messagebox.showinfo("Пусто", "Текст не распознан. Нечего сохранять.")
            self._set_status("Текст не распознан")
            return

        # Показываем форму добавления с предзаполненным текстом
        self._show_add_entry()
        self._add_text.delete("1.0", tk.END)
        self._add_text.insert("1.0", text)
        self._add_topic.insert(0, f"OCR: {Path(image_path).name}")
        self._set_status("Текст распознан. Заполните метаданные и сохраните.", self.FG_GREEN)

    # ─── LLM-редактор ─────────────────────────────────────────────────────

    def _show_editor(self):
        self._clear_content()
        self._current_view = "editor"
        self.page_title.configure(text="LLM-редактор")
        self.page_subtitle.configure(text=f"Модель: {get_ollama_model()}")

        card = tk.Frame(self.content_frame, bg=self.BG_CARD, padx=16, pady=12)
        card.pack(fill=tk.X, padx=8, pady=8)

        tk.Label(
            card,
            text="Вставьте текст для редактирования через LLM. "
            "Редактор исправит ошибки, улучшит читаемость, сохраняя смысл и стиль.",
            font=("Segoe UI", 10),
            bg=self.BG_CARD,
            fg=self.FG_DIM,
            wraplength=700,
            justify="left",
        ).pack(fill=tk.X)

        _, self._editor_input = self._make_text_area(
            self.content_frame, label="Исходный текст:", height=10
        )

        self._make_button_row(
            self.content_frame,
            [("Отредактировать", self._do_edit, "Accent.TButton")],
        )

        _, self._editor_output = self._make_text_area(
            self.content_frame, label="Результат:", height=10
        )

        # Кнопки после результата
        self._make_button_row(
            self.content_frame,
            [
                ("Заменить исходный", self._editor_replace, "Small.TButton"),
                ("Скопировать", self._editor_copy, "Small.TButton"),
            ],
        )

        self._set_status("Вставьте текст и нажмите «Отредактировать»")

    def _do_edit(self):
        """Отправляет текст на LLM-редактирование в фоновом потоке."""
        original = self._editor_input.get("1.0", tk.END).strip()
        if not original:
            messagebox.showwarning("Пусто", "Введите текст для редактирования.")
            return

        self._set_status("Отправляю текст в LLM… Это может занять время", self.FG_YELLOW)
        self._editor_output.delete("1.0", tk.END)
        self._editor_output.insert("1.0", "Обработка… Подождите…")

        def _worker():
            try:
                edited = editor.edit_text(original)
                self.root.after(0, self._edit_done, edited)
            except Exception as e:
                self.root.after(0, self._edit_error, str(e))

        threading.Thread(target=_worker, daemon=True).start()

    def _edit_done(self, text: str):
        self._editor_output.delete("1.0", tk.END)
        self._editor_output.insert("1.0", text)
        self._set_status("Редактирование завершено", self.FG_GREEN)

    def _edit_error(self, error: str):
        self._editor_output.delete("1.0", tk.END)
        self._editor_output.insert("1.0", f"Ошибка: {error}")
        self._set_status(f"Ошибка LLM: {error}", self.FG_RED)

    def _editor_replace(self):
        """Заменяет исходный текст результатом."""
        edited = self._editor_output.get("1.0", tk.END).strip()
        if edited:
            self._editor_input.delete("1.0", tk.END)
            self._editor_input.insert("1.0", edited)
            self._set_status("Исходный текст заменён", self.FG_GREEN)

    def _editor_copy(self):
        """Копирует результат в буфер обмена."""
        edited = self._editor_output.get("1.0", tk.END).strip()
        if edited:
            self.root.clipboard_clear()
            self.root.clipboard_append(edited)
            self._set_status("Скопировано в буфер обмена", self.FG_GREEN)

    def _edit_entry_with_llm(self, entry_id: int):
        """Редактирует запись через LLM."""
        entry = db.get_entry_by_id(self.conn, entry_id)
        if not entry:
            return

        self._show_editor()
        self._editor_input.delete("1.0", tk.END)
        self._editor_input.insert("1.0", entry.get("text", ""))

        # После редактирования — опция сохранить обратно
        def _save_back():
            edited = self._editor_output.get("1.0", tk.END).strip()
            if edited:
                db.update_entry_text(self.conn, entry_id, edited)
                self._set_status(f"Запись #{entry_id} обновлена через LLM", self.FG_GREEN)
                messagebox.showinfo("Готово", f"Запись #{entry_id} обновлена.")
                self._show_entry_detail(entry_id)

        # Добавляем кнопку сохранения
        btn_row = self.content_frame.winfo_children()[-1]
        ttk.Button(
            btn_row,
            text=f"Сохранить в запись #{entry_id}",
            style="Accent.TButton",
            command=_save_back,
        ).pack(side=tk.LEFT, padx=4)

    # ─── Импорт архива ────────────────────────────────────────────────────

    def _show_import(self):
        self._clear_content()
        self._current_view = "import"
        self.page_title.configure(text="Импорт архива")
        self.page_subtitle.configure(text="Загрузите записи из папки с .txt файлами")

        card = tk.Frame(self.content_frame, bg=self.BG_CARD, padx=16, pady=16)
        card.pack(fill=tk.X, padx=8, pady=8)

        file_frame = tk.Frame(card, bg=self.BG_CARD)
        file_frame.pack(fill=tk.X, pady=4)

        tk.Label(
            file_frame,
            text="Папка архива:",
            font=("Segoe UI", 10),
            bg=self.BG_CARD,
            fg=self.FG_DIM,
            width=14,
            anchor="w",
        ).pack(side=tk.LEFT)

        self._import_path = tk.StringVar()
        ttk.Entry(
            file_frame, textvariable=self._import_path, font=("Segoe UI", 10)
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        ttk.Button(
            file_frame,
            text="Обзор…",
            style="Small.TButton",
            command=self._import_browse,
        ).pack(side=tk.LEFT)

        tk.Label(
            card,
            text="Рекурсивно обходит все .txt файлы, извлекает блоки ===...===, "
            "проверяет уникальность и добавляет в БД.",
            font=("Segoe UI", 9),
            bg=self.BG_CARD,
            fg=self.FG_DIM,
            wraplength=700,
            justify="left",
        ).pack(fill=tk.X, pady=(8, 0))

        self._make_button_row(
            self.content_frame,
            [
                ("Импортировать", self._do_import, "Accent.TButton"),
            ],
        )

        # Область результатов импорта
        _, self._import_log = self._make_text_area(
            self.content_frame, label="Лог импорта:", height=12
        )
        self._import_log.configure(state="disabled")

        self._set_status("Укажите папку с архивом")

    def _import_browse(self):
        path = filedialog.askdirectory(title="Выберите папку с архивом")
        if path:
            self._import_path.set(path)

    def _do_import(self):
        folder = self._import_path.get().strip()
        if not folder:
            messagebox.showwarning("Не выбрано", "Укажите путь к папке.")
            return

        if not Path(folder).exists():
            messagebox.showerror("Не найдено", f"Папка не найдена: {folder}")
            return

        self._set_status("Импортирую архив…", self.FG_YELLOW)
        self._import_log.configure(state="normal")
        self._import_log.delete("1.0", tk.END)
        self._import_log.insert("1.0", "Импортирую… Подождите…")

        def _worker():
            try:
                # Перехватываем print из importer
                import io
                import sys

                old_stdout = sys.stdout
                captured = io.StringIO()
                sys.stdout = captured

                stats = importer.import_archive(
                    folder, conn=self.conn, verbose=True
                )

                sys.stdout = old_stdout
                log_text = captured.getvalue()
                self.root.after(0, self._import_done, stats, log_text)
            except Exception as e:
                sys.stdout = old_stdout
                self.root.after(0, self._import_error, str(e))

        threading.Thread(target=_worker, daemon=True).start()

    def _import_done(self, stats: dict, log_text: str):
        self._import_log.configure(state="normal")
        self._import_log.delete("1.0", tk.END)

        result = (
            f"ИМПОРТ ЗАВЕРШЁН\n"
            f"{'─' * 40}\n"
            f"Файлов найдено: {stats['files_found']}\n"
            f"Блоков найдено: {stats['blocks_found']}\n"
            f"Добавлено: {stats['added']}\n"
            f"Дубликатов пропущено: {stats['duplicates']}\n"
            f"Невалидных блоков: {stats['invalid']}\n"
        )
        if stats["errors"]:
            result += f"Ошибок: {len(stats['errors'])}\n"
            for err in stats["errors"]:
                result += f"  — {err}\n"

        if log_text:
            result += f"\n{'─' * 40}\nДетальный лог:\n{log_text}"

        self._import_log.insert("1.0", result)
        self._set_status(
            f"Импорт завершён: добавлено {stats['added']} записей", self.FG_GREEN
        )

    def _import_error(self, error: str):
        self._import_log.configure(state="normal")
        self._import_log.delete("1.0", tk.END)
        self._import_log.insert("1.0", f"Ошибка: {error}")
        self._set_status(f"Ошибка импорта: {error}", self.FG_RED)

    # ─── Экспорт ──────────────────────────────────────────────────────────

    def _handle_export(self):
        dumps = db.get_all_raw_dumps(self.conn)
        if not dumps:
            messagebox.showinfo("Пусто", "Нет записей для экспорта.")
            return

        filepath = filedialog.asksaveasfilename(
            title="Экспорт записей",
            defaultextension=".txt",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")],
            initialfile="journal_export.txt",
        )
        if not filepath:
            return

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                for dump in dumps:
                    f.write(dump + "\n\n")
            self._set_status(
                f"Экспортировано {len(dumps)} записей в {filepath}", self.FG_GREEN
            )
            messagebox.showinfo(
                "Готово", f"Экспортировано {len(dumps)} записей в\n{filepath}"
            )
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить файл: {e}")
            self._set_status(f"Ошибка экспорта: {e}", self.FG_RED)

    # ─── Удаление записи ──────────────────────────────────────────────────

    def _delete_entry(self, entry_id: int, entry_date: str):
        if not messagebox.askyesno(
            "Удаление",
            f"Удалить запись #{entry_id} от {entry_date}?\n"
            "Это также удалит связи с тэгами.",
        ):
            return

        # Удаляем конкретную запись
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
        self.conn.commit()

        # Очищаем неиспользуемые теги
        cursor.execute(
            "DELETE FROM tags WHERE id NOT IN (SELECT tag_id FROM entry_tags)"
        )
        self.conn.commit()

        self._set_status(f"Запись #{entry_id} удалена", self.FG_ORANGE)
        self._show_recent()

    # ─── Закрытие приложения ──────────────────────────────────────────────

    def _on_close(self):
        if self.conn:
            self.conn.close()
        self.root.destroy()


# ─── Точка входа ───────────────────────────────────────────────────────────────

def run_gui(db_path: Optional[str] = None):
    """Запускает графический интерфейс дневника."""
    root = tk.Tk()
    try:
        # Пытаемся установить иконку (если есть)
        root.iconname("Дневник")
    except Exception:
        pass

    app = JournalApp(root, db_path=db_path)
    root.mainloop()


if __name__ == "__main__":
    run_gui()
