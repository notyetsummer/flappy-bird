"""
Подготовка ассетов для платформера.

Что делает скрипт:
1. Создаёт структуру папок assets/.
2. Генерирует базовый набор пиксель-арт ассетов (CC0, авторство — этот проект),
   чтобы игра сразу запускалась со спрайтами, а не примитивами.
3. Пишет assets/licenses/asset_sources.md и licenses.json.

Почему ассеты генерируются, а не скачиваются:
   Автоматическая загрузка чужих наборов (Kenney/OpenGameArt/itch.io) требует
   ручной проверки лицензии и подтверждения на сайте. Чтобы не нарушать правила
   источников и лицензии, по умолчанию используются собственные CC0-плейсхолдеры.
   Как заменить их «настоящими» ассетами Kenney — см. инструкцию ниже и
   assets/licenses/asset_sources.md.

Запуск:
    python scripts/setup_assets.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# Генерация изображений не должна требовать окна.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent
ASSETS = BASE_DIR / "assets"

SUBDIRS = [
    "raw_downloads",
    "backgrounds",
    "player",
    "enemies",
    "tiles",
    "obstacles",
    "items",
    "ui",
    "licenses",
]

# --- палитра ---
TRANSPARENT = (0, 0, 0, 0)
OUTLINE = (28, 24, 40)


def _surf(w: int, h: int) -> pygame.Surface:
    return pygame.Surface((w, h), pygame.SRCALPHA)


def _save(surf: pygame.Surface, rel: str) -> None:
    path = ASSETS / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(surf, str(path))


def _outline(surf: pygame.Surface, color=OUTLINE) -> None:
    pygame.draw.rect(surf, color, surf.get_rect(), 1)


# ---------- генераторы спрайтов (база 16x16, кроме фона/флага) ----------

def make_player(frame: str) -> pygame.Surface:
    s = _surf(16, 16)
    body = (70, 130, 220)
    dark = (40, 90, 180)
    skin = (245, 220, 180)
    # ноги (анимируются для бега)
    if frame == "run_0":
        legs = [(4, 13, 3, 3), (9, 12, 3, 4)]
    elif frame == "run_1":
        legs = [(4, 12, 3, 4), (9, 13, 3, 3)]
    elif frame == "run_2":
        legs = [(3, 13, 3, 3), (10, 12, 3, 4)]
    elif frame == "run_3":
        legs = [(5, 12, 3, 4), (8, 13, 3, 3)]
    elif frame in ("jump", "fall"):
        legs = [(4, 12, 3, 3), (9, 12, 3, 3)]
    else:  # idle
        legs = [(4, 13, 3, 3), (9, 13, 3, 3)]
    for lx, ly, lw, lh in legs:
        pygame.draw.rect(s, dark, (lx, ly, lw, lh))
    # туловище
    pygame.draw.rect(s, body, (3, 6, 10, 7))
    pygame.draw.rect(s, dark, (3, 6, 10, 7), 1)
    # голова
    pygame.draw.rect(s, skin, (4, 1, 8, 6))
    pygame.draw.rect(s, OUTLINE, (4, 1, 8, 6), 1)
    # глаз (смотрит вправо)
    pygame.draw.rect(s, OUTLINE, (9, 3, 2, 2))
    if frame == "jump":
        pygame.draw.rect(s, body, (1, 5, 2, 4))  # рука вверх
    return s


def make_tile(kind: str) -> pygame.Surface:
    s = _surf(16, 16)
    if kind == "ground":
        s.fill((110, 75, 45))
        pygame.draw.rect(s, (80, 52, 30), (0, 0, 16, 16), 1)
        for bx, by in [(2, 3), (9, 4), (5, 9), (11, 11), (1, 12)]:
            pygame.draw.rect(s, (70, 46, 26), (bx, by, 2, 2))
    elif kind == "grass":
        s.fill((110, 75, 45))
        pygame.draw.rect(s, (95, 175, 70), (0, 0, 16, 5))
        pygame.draw.rect(s, (70, 140, 55), (0, 4, 16, 2))
        for bx in range(0, 16, 4):
            pygame.draw.rect(s, (120, 200, 90), (bx, 0, 2, 2))
    elif kind == "stone":
        s.fill((120, 120, 135))
        pygame.draw.rect(s, (90, 90, 105), (0, 0, 16, 16), 1)
        pygame.draw.line(s, (90, 90, 105), (0, 8), (16, 8))
        pygame.draw.line(s, (90, 90, 105), (8, 0), (8, 8))
        pygame.draw.line(s, (90, 90, 105), (4, 8), (4, 16))
    else:  # dirt
        s.fill((120, 82, 50))
        pygame.draw.rect(s, (90, 60, 36), (0, 0, 16, 16), 1)
    return s


def make_coin(frame: int) -> pygame.Surface:
    s = _surf(16, 16)
    widths = [6, 4, 2, 4]  # вращение
    w = widths[frame % 4]
    cx = 8
    pygame.draw.ellipse(s, (255, 205, 40), (cx - w, 2, w * 2, 12))
    pygame.draw.ellipse(s, (255, 235, 150), (cx - w, 2, w * 2, 12), 1)
    if w >= 4:
        pygame.draw.rect(s, (255, 235, 150), (cx - 1, 5, 2, 6))
    return s


def make_spikes() -> pygame.Surface:
    s = _surf(16, 16)
    color = (200, 60, 60)
    for i in range(4):
        x0 = i * 4
        pygame.draw.polygon(
            s, color, [(x0, 16), (x0 + 2, 4), (x0 + 4, 16)]
        )
        pygame.draw.polygon(
            s, (120, 30, 30), [(x0, 16), (x0 + 2, 4), (x0 + 4, 16)], 1
        )
    return s


def make_slime(frame: int) -> pygame.Surface:
    s = _surf(16, 16)
    squash = 0 if frame == 0 else 2
    top = 6 + squash
    pygame.draw.ellipse(s, (90, 200, 110), (1, top, 14, 16 - top))
    pygame.draw.ellipse(s, (60, 160, 80), (1, top, 14, 16 - top), 1)
    pygame.draw.rect(s, OUTLINE, (5, top + 2, 2, 2))
    pygame.draw.rect(s, OUTLINE, (9, top + 2, 2, 2))
    return s


def make_flag() -> pygame.Surface:
    s = _surf(16, 32)
    pygame.draw.rect(s, (180, 180, 190), (2, 0, 2, 32))  # шест
    pygame.draw.polygon(s, (90, 220, 120), [(4, 2), (14, 6), (4, 11)])  # флажок
    return s


def make_background() -> pygame.Surface:
    s = pygame.Surface((480, 270))
    for y in range(270):
        t = y / 270
        c = (
            int(120 * (1 - t) + 60 * t),
            int(180 * (1 - t) + 120 * t),
            int(230 * (1 - t) + 150 * t),
        )
        pygame.draw.line(s, c, (0, y), (480, y))
    # дальние холмы
    pygame.draw.ellipse(s, (90, 160, 110), (-40, 180, 280, 180))
    pygame.draw.ellipse(s, (80, 145, 100), (200, 200, 360, 180))
    # облака
    for cx, cy in [(80, 50), (300, 80), (400, 40)]:
        pygame.draw.ellipse(s, (245, 250, 255), (cx, cy, 70, 28))
        pygame.draw.ellipse(s, (245, 250, 255), (cx + 24, cy - 10, 60, 26))
    return s


def make_heart(full: bool) -> pygame.Surface:
    s = _surf(16, 16)
    color = (225, 60, 70) if full else (90, 60, 65)
    pygame.draw.circle(s, color, (5, 6), 4)
    pygame.draw.circle(s, color, (11, 6), 4)
    pygame.draw.polygon(s, color, [(1, 7), (15, 7), (8, 15)])
    return s


def make_missing() -> pygame.Surface:
    s = _surf(16, 16)
    s.fill((255, 0, 220))
    for y in range(0, 16, 8):
        for x in range(0, 16, 8):
            pygame.draw.rect(s, (20, 20, 20), (x, y, 8, 8))
            pygame.draw.rect(s, (20, 20, 20), (x + 4, y + 4, 4, 4))
    return s


def generate_all() -> list[str]:
    created: list[str] = []

    def emit(surf: pygame.Surface, rel: str) -> None:
        _save(surf, rel)
        created.append(rel)

    # игрок
    emit(make_player("idle"), "player/idle_0.png")
    emit(make_player("idle"), "player/idle_1.png")
    for i in range(4):
        emit(make_player(f"run_{i}"), f"player/run_{i}.png")
    emit(make_player("jump"), "player/jump.png")
    emit(make_player("fall"), "player/fall.png")

    # тайлы
    for kind in ("ground", "grass", "stone", "dirt"):
        emit(make_tile(kind), f"tiles/{kind}.png")

    # монеты
    for i in range(4):
        emit(make_coin(i), f"items/coin_{i}.png")

    # препятствия
    emit(make_spikes(), "obstacles/spikes.png")

    # враги
    emit(make_slime(0), "enemies/slime_idle_0.png")
    emit(make_slime(1), "enemies/slime_idle_1.png")

    # прочее
    emit(make_flag(), "items/flag.png")
    emit(make_background(), "backgrounds/default.png")
    emit(make_heart(True), "ui/heart_full.png")
    emit(make_heart(False), "ui/heart_empty.png")
    emit(make_missing(), "ui/missing.png")

    return created


def write_licenses(created: list[str]) -> None:
    md = ASSETS / "licenses" / "asset_sources.md"
    js = ASSETS / "licenses" / "licenses.json"
    md.parent.mkdir(parents=True, exist_ok=True)

    md.write_text(
        "# Источники ассетов\n\n"
        "## Generated Pixel Placeholder Pack\n\n"
        "- Source: сгенерировано scripts/setup_assets.py (этот проект)\n"
        "- Author: проект (procedural)\n"
        "- License: CC0 / Public Domain\n"
        "- Usage status: integrated\n"
        "- Notes: базовый набор спрайтов (игрок, тайлы, монета, шипы, слайм, "
        "фон, флаг, UI). Создан кодом, поэтому свободен от лицензионных рисков.\n\n"
        "## Как заменить на ассеты Kenney (опционально, выше качеством)\n\n"
        "1. Скачай вручную CC0-набор, например Kenney Pixel Platformer:\n"
        "   https://kenney.nl/assets/pixel-platformer\n"
        "2. Положи архив в `assets/raw_downloads/` и распакуй.\n"
        "3. Скопируй нужные PNG в рабочие папки `assets/player`, `assets/tiles`, "
        "`assets/items`, `assets/enemies`, `assets/obstacles`, `assets/backgrounds`, "
        "сохранив имена файлов из `src/assets/asset_registry.py` "
        "(или поправь пути в реестре).\n"
        "4. Добавь запись об источнике и лицензии Kenney (CC0) в этот файл и в "
        "`licenses.json`.\n\n"
        "Не используй ассеты с пометками personal-use-only / no-commercial / "
        "требующие покупки. При неясной лицензии — пропусти ассет.\n",
        encoding="utf-8",
    )

    data = [
        {
            "name": "Generated Pixel Placeholder Pack",
            "source_url": "local:scripts/setup_assets.py",
            "author": "project (procedural)",
            "license": "CC0",
            "status": "integrated",
            "notes": "Base sprites generated in-code; safe to use and redistribute.",
            "files": created,
        }
    ]
    js.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    pygame.init()
    for d in SUBDIRS:
        (ASSETS / d).mkdir(parents=True, exist_ok=True)
    created = generate_all()
    write_licenses(created)
    pygame.quit()
    print(f"[setup_assets] Создано ассетов: {len(created)}")
    print(f"[setup_assets] Папка: {ASSETS}")
    print("[setup_assets] Лицензии: assets/licenses/asset_sources.md")
    print("[setup_assets] Готово. Запусти игру: python main.py")


if __name__ == "__main__":
    main()
