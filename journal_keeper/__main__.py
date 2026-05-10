"""
Точка входа: запуск CLI или GUI дневника.

Использование:
    python -m journal_keeper          → CLI-режим (по умолчанию)
    python -m journal_keeper --gui    → графический интерфейс
"""

import sys


def main():
    if "--gui" in sys.argv:
        from .gui import run_gui
        run_gui()
    else:
        from .cli import run
        run()


if __name__ == "__main__":
    main()
