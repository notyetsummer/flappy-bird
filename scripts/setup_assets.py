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
import math
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


# ---------- генераторы спрайтов (база 16x16, игрок 24x24) ----------

# палитра персонажа
P_SKIN = (245, 205, 165)
P_HAIR = (60, 42, 34)
P_SHIRT = (80, 140, 235)
P_SHIRT_D = (50, 100, 190)
P_PANTS = (70, 72, 95)
P_PANTS_D = (48, 50, 68)
P_BOOT = (38, 38, 50)
P_SCARF = (225, 80, 92)


def _limb(s, p0, p1, color, w):
    pygame.draw.line(s, color, (int(p0[0]), int(p0[1])), (int(p1[0]), int(p1[1])), w)


def make_player(state: str, i: int = 0, total: int = 1) -> pygame.Surface:
    """Анимированный человечек 24x24 с конечностями (бег/idle/прыжок/падение)."""
    s = _surf(24, 24)
    cx = 12
    if state == "run":
        ph = (i / total) * 2 * math.pi
        leg = math.sin(ph) * 4.5
        arm = -math.sin(ph) * 4.0
        bob = -abs(math.cos(ph)) * 1.6
        lean = 2
    elif state == "idle":
        ph = (i / max(1, total)) * 2 * math.pi
        bob = math.sin(ph) * 1.0
        leg = 0.0
        arm = math.sin(ph) * 0.6
        lean = 0
    elif state == "jump":
        leg, arm, bob, lean = -3.0, -5.0, -1.0, 1
    elif state == "fall":
        leg, arm, bob, lean = 3.0, 5.0, 1.0, 1
    else:
        leg = arm = bob = 0.0
        lean = 0

    top = int(4 + bob)
    sh_y = top + 7
    hip_y = top + 13

    # ноги
    for sign in (-1, 1):
        dx = sign * leg
        hipx = cx + sign * 2
        knee = (hipx + dx / 2, hip_y + 4)
        foot = (hipx + dx, hip_y + 8)
        _limb(s, (hipx, hip_y), knee, P_PANTS, 4)
        _limb(s, knee, foot, P_PANTS_D, 4)
        pygame.draw.rect(s, P_BOOT, (int(foot[0]) - 2, int(foot[1]) - 1, 5, 3))

    # дальняя рука (за телом)
    back = (cx - 4, sh_y)
    back_h = (cx - 4 - arm, sh_y + 8)
    _limb(s, back, (back[0] - arm / 2, sh_y + 4), P_SHIRT_D, 3)
    _limb(s, (back[0] - arm / 2, sh_y + 4), back_h, P_SKIN, 3)

    # туловище
    pygame.draw.rect(s, P_SHIRT, (cx - 4 + lean, sh_y - 1, 8, 9), border_radius=2)
    pygame.draw.rect(s, P_SHIRT_D, (cx - 4 + lean, sh_y - 1, 8, 9), 1, border_radius=2)

    # шарф (развевается)
    tail = abs(leg) + (3 if state in ("run", "fall") else 1)
    pygame.draw.polygon(s, P_SCARF, [
        (cx - 3 + lean, sh_y),
        (cx - 7 + lean - int(arm), sh_y + 2 + int(tail)),
        (cx - 2 + lean, sh_y + 3),
    ])

    # передняя рука
    sh = (cx + 4 + lean, sh_y)
    elbow = (sh[0] + arm / 2, sh_y + 4)
    hand = (sh[0] + arm, sh_y + 8)
    _limb(s, sh, elbow, P_SHIRT, 3)
    _limb(s, elbow, hand, P_SKIN, 3)

    # голова
    hx = cx + lean
    pygame.draw.circle(s, P_SKIN, (hx, top + 2), 4)
    pygame.draw.circle(s, OUTLINE, (hx, top + 2), 4, 1)
    pygame.draw.rect(s, P_HAIR, (hx - 4, top - 2, 8, 4), border_radius=2)
    pygame.draw.rect(s, OUTLINE, (hx + 1, top + 1, 2, 2))  # глаз вправо
    return s


def make_player_death(i: int, total: int = 8) -> pygame.Surface:
    """Кадры смерти: персонаж падает набок (для default_player)."""
    s = _surf(24, 24)
    t = i / max(1, total - 1)
    # наклон и «сплющивание» к концу
    tilt = int(t * 6)
    squash = int(t * 3)
    cx, base_y = 12 + tilt // 2, 20 - squash // 2
    body_w = max(4, 8 - squash // 2)
    body_h = max(3, 9 - squash)
    pygame.draw.rect(
        s, P_SHIRT, (cx - body_w // 2, base_y - body_h - 4, body_w, body_h), border_radius=2
    )
    pygame.draw.circle(s, P_SKIN, (cx + tilt, base_y - body_h - 6), max(2, 4 - squash // 2))
    if t > 0.5:
        # «X» глаза
        ex, ey = cx + tilt, base_y - body_h - 7
        pygame.draw.line(s, OUTLINE, (ex - 2, ey - 1), (ex, ey + 1), 1)
        pygame.draw.line(s, OUTLINE, (ex, ey - 1), (ex - 2, ey + 1), 1)
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


def make_saw() -> pygame.Surface:
    s = _surf(32, 32)
    cx = cy = 16
    steel, steel_d, hub = (200, 205, 215), (130, 135, 150), (90, 95, 110)
    teeth = 12
    outer, inner = 15, 11
    pts = []
    for i in range(teeth * 2):
        ang = math.pi * i / teeth
        rad = outer if i % 2 == 0 else inner
        pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    pygame.draw.polygon(s, steel, pts)
    pygame.draw.polygon(s, steel_d, pts, 1)
    pygame.draw.circle(s, hub, (cx, cy), 6)
    pygame.draw.circle(s, (60, 64, 78), (cx, cy), 6, 1)
    pygame.draw.circle(s, (40, 44, 56), (cx, cy), 2)
    return s


def make_slime(frame: int) -> pygame.Surface:
    s = _surf(16, 16)
    # пульсация: 4 кадра дыхания/прыжочка
    squash = [0, 2, 3, 1][frame % 4]
    top = 5 + squash
    width = 14 + (3 - squash)
    x0 = (16 - width) // 2
    pygame.draw.ellipse(s, (90, 200, 110), (x0, top, width, 16 - top))
    pygame.draw.ellipse(s, (60, 160, 80), (x0, top, width, 16 - top), 1)
    pygame.draw.ellipse(s, (150, 230, 160), (x0 + 2, top + 1, width - 6, 3))  # блик
    blink = frame % 4 == 2
    eh = 1 if blink else 2
    pygame.draw.rect(s, OUTLINE, (5, top + 3, 2, eh))
    pygame.draw.rect(s, OUTLINE, (9, top + 3, 2, eh))
    return s


def make_gem(frame: int) -> pygame.Surface:
    s = _surf(16, 16)
    col, hi, dk = (90, 210, 235), (210, 250, 255), (40, 150, 185)
    pts = [(8, 1), (14, 7), (8, 15), (2, 7)]
    pygame.draw.polygon(s, col, pts)
    pygame.draw.polygon(s, dk, pts, 1)
    pygame.draw.line(s, hi, (8, 2), (5, 7), 1)
    pygame.draw.line(s, dk, (8, 14), (12, 7), 1)
    if frame % 4 in (1, 3):  # блестит
        pygame.draw.line(s, (255, 255, 255), (12, 2), (12, 4))
        pygame.draw.line(s, (255, 255, 255), (11, 3), (13, 3))
    return s


def make_key() -> pygame.Surface:
    s = _surf(16, 16)
    g, gd = (240, 205, 70), (190, 150, 40)
    pygame.draw.circle(s, g, (5, 6), 4, 2)
    pygame.draw.circle(s, gd, (5, 6), 4, 1)
    pygame.draw.rect(s, g, (8, 5, 7, 2))
    pygame.draw.rect(s, g, (12, 7, 2, 3))
    pygame.draw.rect(s, g, (14, 7, 2, 2))
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
    # солнце с гало
    pygame.draw.circle(s, (255, 245, 200), (400, 60), 26)
    pygame.draw.circle(s, (255, 235, 160), (400, 60), 20)
    # дальние горы (силуэт)
    pygame.draw.polygon(s, (120, 150, 180), [(0, 200), (90, 120), (180, 200)])
    pygame.draw.polygon(s, (110, 140, 170), [(120, 200), (240, 110), (360, 200)])
    # холмы ближе
    pygame.draw.ellipse(s, (95, 170, 115), (-40, 180, 300, 200))
    pygame.draw.ellipse(s, (80, 150, 100), (200, 200, 380, 200))
    # облака
    for cx, cy in [(80, 50), (300, 90), (180, 40)]:
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

    # игрок: idle (4), бег (6), прыжок, падение
    for i in range(4):
        emit(make_player("idle", i, 4), f"player/idle_{i}.png")
    for i in range(6):
        emit(make_player("run", i, 6), f"player/run_{i}.png")
    emit(make_player("jump"), "player/jump.png")
    emit(make_player("fall"), "player/fall.png")
    for i in range(8):
        emit(make_player_death(i, 8), f"player/death_{i}.png")

    # тайлы
    for kind in ("ground", "grass", "stone", "dirt"):
        emit(make_tile(kind), f"tiles/{kind}.png")

    # монеты
    for i in range(4):
        emit(make_coin(i), f"items/coin_{i}.png")

    # самоцветы и ключ
    for i in range(4):
        emit(make_gem(i), f"items/gem_{i}.png")
    emit(make_key(), "items/key.png")

    # препятствия
    emit(make_spikes(), "obstacles/spikes.png")
    emit(make_saw(), "obstacles/saw.png")

    # враги (4 кадра дыхания)
    for i in range(4):
        emit(make_slime(i), f"enemies/slime_idle_{i}.png")

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
