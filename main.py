"""
Точка входа в платформер.

    python main.py                       # меню выбора уровней
    python main.py --level levels/level_001.json   # запуск уровня из JSON
    python main.py --editor              # редактор уровней
    python main.py --debug-hitboxes      # с отрисовкой хитбоксов

Это тонкая обёртка над platformer.main(), чтобы соответствовать ТЗ
(python main.py ...). Сам движок и игровая логика — в platformer.py.
"""

from __future__ import annotations

from platformer import main

if __name__ == "__main__":
    main()
