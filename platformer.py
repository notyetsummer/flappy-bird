"""
Платформер на pygame: движение, прыжок, сбор монет, два уровня.
Только stdlib + pygame (без доп. установки кроме pygame).
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable

import pygame

# --- экран ---
W, H = 960, 540
FPS = 60
DT = 1.0 / FPS

# Debug: отрисовка хитбоксов поверх спрайтов (по умолчанию выключено)
DEBUG_DRAW_HITBOXES = False

# Слой ассетов подключается лениво и безопасно: если его нет — рисуем примитивы.
try:
    from src.assets.asset_registry import DEFAULT_PLAYER_SKIN, get_asset_manager as _get_asset_manager
except Exception:  # noqa: BLE001 — отсутствие ассет-слоя не должно ронять игру
    _get_asset_manager = None  # type: ignore[assignment]
    DEFAULT_PLAYER_SKIN = "pink_monster"

# --- цвета ---
SKY = (135, 206, 235)
SKY2 = (90, 60, 110)
GROUND = (76, 153, 76)
GROUND2 = (60, 90, 70)
PLATFORM = (139, 90, 43)
PLATFORM_TOP = (160, 120, 60)
SPIKE = (200, 50, 50)
COIN = (255, 215, 0)
COIN_SHINE = (255, 245, 180)
PLAYER = (50, 120, 220)
PLAYER_ACCENT = (30, 80, 180)
UI = (255, 255, 255)
UI_DIM = (200, 200, 210)
GOAL = (100, 255, 150)
PORTAL = (170, 90, 230)
PORTAL_CORE = (235, 200, 255)
GATE_CLOSED = (200, 170, 60)
GATE_FRAME = (120, 100, 30)
BUTTON_UP = (200, 60, 60)
BUTTON_DOWN = (80, 200, 100)
GRAV_ACCENT = (255, 150, 60)
POWERUP = (80, 220, 255)
POWERUP_CORE = (220, 250, 255)
SAW = (210, 210, 220)
SAW_CORE = (90, 95, 110)
TURRET = (90, 100, 120)
PROJECTILE = (255, 90, 60)


class GameState(Enum):
    LEVEL_SELECT = auto()
    PLAYING = auto()
    LEVEL_COMPLETE = auto()
    WIN = auto()
    DEAD = auto()


# --- game feel (секунды / пиксели за кадр при 60 FPS) ---
class Feel:
    GRAVITY = 0.55
    FALL_GRAVITY_MULT = 1.35  # быстрее падаем на пике прыжка — «снappy» arc
    MAX_FALL = 14.0

    MOVE_SPEED = 5.2
    GROUND_ACCEL = 0.85
    GROUND_FRICTION = 0.82
    AIR_ACCEL = 0.45
    AIR_FRICTION = 0.92

    JUMP_VELOCITY = -11.8
    JUMP_CUT_MULT = 0.42  # отпустили прыжок раньше — ниже прыжок
    COYOTE_TIME = 0.10
    JUMP_BUFFER = 0.12
    PLAYER_W = 28
    PLAYER_H = 36


# Длительность кадров анимации игрока (секунды, не FPS).
# Idle: асимметричный цикл «дыхания» ~1.4 с — 400/300/400/300 ms на кадр
# (рекомендации pixel-art: sprite-ai.art/guides/animation-principles).
PLAYER_ANIM_DURATIONS: dict[str, list[float]] = {
    "idle": [0.40, 0.30, 0.40, 0.30],
    "run": [0.10, 0.10, 0.10, 0.10, 0.10, 0.10],
    "jump": [0.08, 0.10, 0.14, 0.10],
    "fall": [0.10, 0.12, 0.14, 0.12],
    "death": [0.09, 0.09, 0.10, 0.10, 0.11, 0.12, 0.14, 0.18],
}
PLAYER_ANIM_FRAME_COUNTS: dict[str, int] = {
    "idle": 4,
    "run": 6,
    "jump": 4,
    "fall": 4,
    "death": 8,
}
PLAYER_ANIM_DEFAULT_DURATION = 0.15
# Допуск «стояния на полу» (px): без него feet=492 и platform.top=492
# не дают colliderect, гравитация дёргает персонажа idle↔fall каждый кадр.
GROUND_SNAP = 3


@dataclass
class RectObj:
    x: float
    y: float
    w: float
    h: float
    tile_id: str = "grass"  # какой тайл/спрайт рисовать (визуал, не физика)

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x), int(self.y), int(self.w), int(self.h))


@dataclass
class CoinObj:
    x: float
    y: float
    radius: float = 10.0
    collected: bool = False


@dataclass
class Portal:
    """Зона входа; при касании переносит игрока в (tx, ty) — левый-верхний угол."""

    x: float
    y: float
    w: float
    h: float
    tx: float
    ty: float

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x), int(self.y), int(self.w), int(self.h))


@dataclass
class Button:
    """Кнопка: при нажатии F рядом — открывает ворота уровня."""

    x: float
    y: float
    w: float
    h: float
    pressed: bool = False

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x), int(self.y), int(self.w), int(self.h))


@dataclass
class Gate:
    """Ворота: пока не открыты — твёрдая стена, перекрывающая проход."""

    x: float
    y: float
    w: float
    h: float
    opened: bool = False

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x), int(self.y), int(self.w), int(self.h))


@dataclass
class PowerUp:
    """Бонус. kind='lowgrav' — на duration секунд уменьшает гравитацию вдвое."""

    x: float
    y: float
    kind: str = "lowgrav"
    duration: float = 30.0
    radius: float = 14.0
    collected: bool = False

    @property
    def rect(self) -> pygame.Rect:
        r = int(self.radius)
        return pygame.Rect(int(self.x - r), int(self.y - r), r * 2, r * 2)


@dataclass
class Saw:
    """Вращающаяся пила, курсирующая между (x1,y1) и (x2,y2) по синусоиде."""

    x1: float
    y1: float
    x2: float
    y2: float
    r: float = 26.0
    period: float = 2.4
    phase: float = 0.0

    def pos(self, t: float) -> tuple[float, float]:
        k = (math.sin(2 * math.pi * (t / self.period) + self.phase) + 1) / 2
        return (self.x1 + (self.x2 - self.x1) * k, self.y1 + (self.y2 - self.y1) * k)


@dataclass
class Turret:
    """Турель: периодически выпускает шип-снаряд в направлении (dx, dy)."""

    x: float
    y: float
    dx: float
    dy: float
    interval: float = 1.4
    speed: float = 4.2
    phase: float = 0.0
    timer: float = 0.0


@dataclass
class Projectile:
    x: float
    y: float
    vx: float
    vy: float
    r: float = 7.0


@dataclass
class Enemy:
    """Простой враг (слайм): патрулирует по X между patrol_left/right, летален."""

    x: float
    y: float
    enemy_type: str = "slime"
    asset_id: str = "slime"
    patrol_left: float = 0.0
    patrol_right: float = 0.0
    speed: float = 1.4
    w: float = 32.0
    h: float = 28.0
    direction: int = 1

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x), int(self.y), int(self.w), int(self.h))


@dataclass
class LevelData:
    name: str
    world_w: int
    spawn: tuple[float, float]
    world_h: int = H
    platforms: list[RectObj] = field(default_factory=list)
    spikes: list[RectObj] = field(default_factory=list)
    spikes_down: list[RectObj] = field(default_factory=list)
    coins: list[CoinObj] = field(default_factory=list)
    portals: list[Portal] = field(default_factory=list)
    buttons: list[Button] = field(default_factory=list)
    gates: list[Gate] = field(default_factory=list)
    powerups: list[PowerUp] = field(default_factory=list)
    saws: list[Saw] = field(default_factory=list)
    turrets: list[Turret] = field(default_factory=list)
    enemies: list[Enemy] = field(default_factory=list)
    goal: RectObj | None = None
    bg_top: tuple[int, int, int] = SKY
    bg_bottom: tuple[int, int, int] = GROUND
    plat_color: tuple[int, int, int] = PLATFORM
    plat_top_color: tuple[int, int, int] = PLATFORM_TOP
    background: str | None = None  # id фонового спрайта (если есть ассеты)
    player_asset_set: str = DEFAULT_PLAYER_SKIN


def level_1() -> LevelData:
    """Уровень 1: цепочка платформ слева направо, ямы со шипами, монеты вверху."""
    p: list[RectObj] = []
    s: list[RectObj] = []
    c: list[CoinObj] = []

    # пол и стартовая площадка
    p.append(RectObj(0, H - 48, 220, 48))
    # серия платформ через экран
    steps = [
        (200, H - 120, 100, 20),
        (340, H - 180, 90, 20),
        (470, H - 140, 80, 20),
        (590, H - 200, 100, 20),
        (720, H - 160, 85, 20),
        (850, H - 220, 95, 20),
        (1000, H - 180, 110, 20),
        (1150, H - 140, 90, 20),
        (1280, H - 100, 120, 20),
        (1450, H - 48, 200, 48),
    ]
    p.extend(RectObj(*t) for t in steps)

    # нижние «острова» под сложными прыжками
    p.append(RectObj(380, H - 70, 60, 16))
    p.append(RectObj(760, H - 90, 55, 16))

    # ямы со шипами на полу между платформами
    spike_pits = [
        (220, H - 24, 120, 24),
        (440, H - 24, 50, 24),
        (670, H - 24, 50, 24),
        (935, H - 24, 65, 24),
        (1240, H - 24, 40, 24),
    ]
    s.extend(RectObj(*t) for t in spike_pits)

    # монеты: над ямами, на вершинах, в углах
    coins_pos = [
        (250, H - 160),
        (385, H - 220),
        (515, H - 180),
        (640, H - 250),
        (755, H - 210),
        (900, H - 270),
        (1050, H - 230),
        (1180, H - 190),
        (1320, H - 150),
        (410, H - 110),
        (790, H - 130),
    ]
    c.extend(CoinObj(x, y) for x, y in coins_pos)

    goal = RectObj(1520, H - 120, 40, 72)
    return LevelData(
        name="Зелёные холмы",
        world_w=1600,
        spawn=(40.0, float(H - 48 - Feel.PLAYER_H)),
        platforms=p,
        spikes=s,
        coins=c,
        goal=goal,
    )


def level_2() -> LevelData:
    """Уровень 2: выше, уже, больше шипов и вертикальных секций."""
    p: list[RectObj] = []
    s: list[RectObj] = []
    c: list[CoinObj] = []

    p.append(RectObj(0, H - 40, 160, 40))
    p.append(RectObj(180, H - 100, 70, 18))
    p.append(RectObj(290, H - 160, 65, 18))
    p.append(RectObj(400, H - 120, 55, 18))
    # узкий мост над ямой
    p.append(RectObj(500, H - 200, 45, 14))
    p.append(RectObj(600, H - 260, 50, 14))
    p.append(RectObj(710, H - 200, 48, 14))
    p.append(RectObj(820, H - 140, 60, 18))
    p.append(RectObj(930, H - 220, 42, 14))
    p.append(RectObj(1040, H - 280, 48, 14))
    p.append(RectObj(1150, H - 220, 50, 14))
    p.append(RectObj(1260, H - 170, 55, 18))
    p.append(RectObj(1370, H - 240, 45, 14))
    p.append(RectObj(1480, H - 300, 50, 14))
    p.append(RectObj(1590, H - 200, 70, 18))
    p.append(RectObj(1700, H - 120, 90, 18))
    p.append(RectObj(1820, H - 48, 180, 48))

    # высокие полки для монет
    p.append(RectObj(350, H - 280, 40, 12))
    p.append(RectObj(880, H - 340, 38, 12))
    p.append(RectObj(1420, H - 360, 40, 12))

    spike_pits = [
        (160, H - 22, 20, 22),
        (250, H - 22, 40, 22),
        (365, H - 22, 35, 22),
        (455, H - 22, 45, 22),
        (545, H - 22, 55, 22),
        (650, H - 22, 60, 22),
        (758, H - 22, 62, 22),
        (868, H - 22, 62, 22),
        (972, H - 22, 68, 22),
        (1088, H - 22, 52, 22),
        (1200, H - 22, 60, 22),
        (1315, H - 22, 55, 22),
        (1415, H - 22, 65, 22),
        (1530, H - 22, 60, 22),
        (1650, H - 22, 50, 22),
        (1760, H - 22, 60, 22),
    ]
    s.extend(RectObj(*t) for t in spike_pits)

    # шипы на краю платформ (нужно перепрыгнуть, а не стоять)
    s.append(RectObj(430, H - 138, 25, 18))
    s.append(RectObj(1260, H - 188, 28, 18))

    coins_pos = [
        (210, H - 150),
        (320, H - 210),
        (370, H - 320),
        (530, H - 250),
        (625, H - 310),
        (750, H - 250),
        (870, H - 190),
        (900, H - 380),
        (1000, H - 320),
        (1100, H - 360),
        (1200, H - 280),
        (1400, H - 420),
        (1500, H - 350),
        (1650, H - 260),
        (1750, H - 180),
    ]
    c.extend(CoinObj(x, y) for x, y in coins_pos)

    goal = RectObj(1880, H - 110, 40, 62)
    return LevelData(
        name="Тёмное ущелье",
        world_w=2000,
        spawn=(30.0, float(H - 40 - Feel.PLAYER_H)),
        platforms=p,
        spikes=s,
        coins=c,
        goal=goal,
        bg_top=SKY2,
        bg_bottom=GROUND2,
        plat_color=(80, 70, 90),
        plat_top_color=(110, 100, 120),
    )


def level_3() -> LevelData:
    """Уровень 3 (порталы): ворота в центре блокируют путь. Зайди в портал →
    попадёшь в комнату с кнопкой → нажми F → ворота откроются → вернись и пройди."""
    p: list[RectObj] = []
    s: list[RectObj] = []
    c: list[CoinObj] = []
    portals: list[Portal] = []
    buttons: list[Button] = []
    gates: list[Gate] = []

    world_w = 1500
    floor_top = H - 40
    pw, ph_ = Feel.PLAYER_W, Feel.PLAYER_H

    # --- основной нижний путь ---
    p.append(RectObj(0, floor_top, world_w, 40))
    p.append(RectObj(250, H - 150, 90, 18))
    p.append(RectObj(430, H - 210, 80, 16))
    p.append(RectObj(980, H - 150, 90, 18))
    p.append(RectObj(1120, H - 210, 90, 16))
    p.append(RectObj(1250, H - 150, 90, 18))

    # --- комната с кнопкой (наверху, недостижима прыжком) ---
    room_floor_top = 190
    p.append(RectObj(120, room_floor_top, 330, 16))
    p.append(RectObj(120, 70, 16, 136))  # левая стенка комнаты

    # вход-портал на нижнем пути (обязателен — ворота всё равно закрыты)
    portals.append(
        Portal(560, floor_top - 90, 38, 90, tx=250.0, ty=float(room_floor_top - ph_))
    )
    # обратный портал в комнате — возвращает к воротам (правее входа)
    portals.append(
        Portal(135, room_floor_top - 72, 30, 72, tx=700.0, ty=float(floor_top - ph_))
    )

    # кнопка в комнате
    buttons.append(Button(360, room_floor_top - 18, 46, 18))

    # ворота в центре (высокая стена — не перепрыгнуть)
    gates.append(Gate(820, floor_top - 260, 26, 260))

    # шипы-ямы на пути за воротами
    s.append(RectObj(1020, floor_top - 18, 50, 18))
    s.append(RectObj(1185, floor_top - 18, 50, 18))

    # монеты: труднодоступные в комнате + по пути
    coins_pos = [
        (200, room_floor_top - 40),
        (300, room_floor_top - 40),
        (420, room_floor_top - 40),
        (270, H - 185),
        (455, H - 245),
        (700, H - 95),
        (1010, H - 185),
        (1150, H - 245),
        (1290, H - 185),
    ]
    c.extend(CoinObj(x, y) for x, y in coins_pos)

    goal = RectObj(1390, H - 110, 40, 70)
    return LevelData(
        name="Портальная застава",
        world_w=world_w,
        spawn=(40.0, float(floor_top - ph_)),
        platforms=p,
        spikes=s,
        coins=c,
        portals=portals,
        buttons=buttons,
        gates=gates,
        goal=goal,
        bg_top=(70, 90, 130),
        bg_bottom=(40, 60, 90),
        plat_color=(70, 80, 110),
        plat_top_color=(110, 130, 170),
    )


def level_4() -> LevelData:
    """Уровень 4 (гравитация): коридор «пол ↔ потолок». Нажми G (или Shift),
    стоя на поверхности, чтобы перевернуть гравитацию и ходить по потолку.
    Шипы чередуются на полу и потолке — без переворотов не пройти."""
    p: list[RectObj] = []
    s_up: list[RectObj] = []  # шипы на полу (остриём вверх)
    s_dn: list[RectObj] = []  # шипы на потолке (остриём вниз)
    c: list[CoinObj] = []

    world_w = 1900
    floor_top = H - 40
    ceil_h = 30  # нижняя кромка потолка = ceil_h
    ph_ = Feel.PLAYER_H

    # пол и потолок на всю длину
    p.append(RectObj(0, floor_top, world_w, 40))
    p.append(RectObj(0, 0, world_w, ceil_h))

    # шипы на полу (на этих участках надо идти по потолку)
    floor_spikes = [(280, 240), (920, 240), (1500, 240)]
    s_up.extend(RectObj(x, floor_top - 18, w, 18) for x, w in floor_spikes)

    # шипы на потолке (на этих участках надо идти по полу)
    ceil_spikes = [(600, 260), (1180, 260)]
    s_dn.extend(RectObj(x, ceil_h, w, 18) for x, w in ceil_spikes)

    # монеты у потолка (берутся только в перевёрнутой гравитации)
    ceil_coins = [(380, ceil_h + 40), (440, ceil_h + 40),
                  (1000, ceil_h + 40), (1060, ceil_h + 40),
                  (1600, ceil_h + 40)]
    # монеты у пола (берутся в обычной гравитации, под шипами потолка)
    floor_coins = [(700, floor_top - 40), (760, floor_top - 40),
                   (1280, floor_top - 40), (1340, floor_top - 40)]
    c.extend(CoinObj(x, y) for x, y in ceil_coins + floor_coins)

    goal = RectObj(world_w - 110, floor_top - 70, 40, 70)
    return LevelData(
        name="Перевёртыш",
        world_w=world_w,
        spawn=(40.0, float(floor_top - ph_)),
        platforms=p,
        spikes=s_up,
        spikes_down=s_dn,
        coins=c,
        goal=goal,
        bg_top=(40, 30, 60),
        bg_bottom=(90, 50, 40),
        plat_color=(70, 55, 80),
        plat_top_color=(150, 100, 70),
    )


def level_5() -> LevelData:
    """Уровень 5 (паверап): возьми синий бонус «низкая гравитация» (×0.5 на 30 с)
    и за это время пройди полосу препятствий — вращающиеся пилы и турели,
    стреляющие шипами. Высокие/далёкие прыжки реальны только в низкой гравитации."""
    p: list[RectObj] = []
    s: list[RectObj] = []
    c: list[CoinObj] = []
    powerups: list[PowerUp] = []
    saws: list[Saw] = []
    turrets: list[Turret] = []

    world_w = 2300
    ph_ = Feel.PLAYER_H

    # стартовая площадка с бонусом
    p.append(RectObj(0, H - 40, 360, 40))
    powerups.append(PowerUp(250, H - 80, kind="lowgrav", duration=30.0))

    # цепочка платформ с широкими провалами (между ними — пропасть = смерть)
    steps = [
        (470, H - 120, 120, 18),
        (700, H - 175, 120, 18),
        (940, H - 130, 120, 18),
        (1180, H - 205, 120, 18),
        (1430, H - 150, 120, 18),
        (1670, H - 120, 120, 18),
        (1910, H - 185, 120, 18),
    ]
    p.extend(RectObj(*t) for t in steps)
    # финишная площадка
    p.append(RectObj(2080, H - 70, 220, 70))

    # шипы на некоторых площадках — приземляйся точно
    s.append(RectObj(700, H - 193, 30, 18))   # край P2
    s.append(RectObj(1520, H - 168, 30, 18))  # край P5

    # вращающиеся пилы в провалах и над платформами
    saws.append(Saw(600, H - 90, 600, H - 240, r=26, period=2.0, phase=0.0))      # верт. в 1-м провале
    saws.append(Saw(880, H - 150, 1060, H - 150, r=24, period=2.6, phase=1.0))    # гориз. над P3
    saws.append(Saw(1300, H - 90, 1300, H - 260, r=28, period=2.2, phase=0.5))    # верт. между P4-P5
    saws.append(Saw(1600, H - 150, 1780, H - 150, r=24, period=2.8, phase=2.0))   # гориз. над P6
    saws.append(Saw(2000, H - 110, 2000, H - 300, r=26, period=2.0, phase=1.5))   # верт. перед финишем

    # турели: стреляют шипами поперёк траекторий прыжков
    turrets.append(Turret(430, H - 250, dx=1, dy=0, interval=1.3, speed=4.5))
    turrets.append(Turret(1180, H - 330, dx=0, dy=1, interval=1.1, speed=4.8, phase=0.4))
    turrets.append(Turret(2050, H - 250, dx=-1, dy=0, interval=1.2, speed=5.0, phase=0.8))

    # монеты-награды на высоте (берутся только во «флоут»-прыжках)
    coins_pos = [
        (530, H - 230),
        (760, H - 290),
        (1000, H - 250),
        (1240, H - 320),
        (1490, H - 270),
        (1730, H - 240),
        (1970, H - 300),
    ]
    c.extend(CoinObj(x, y) for x, y in coins_pos)

    goal = RectObj(2230, H - 140, 40, 70)
    return LevelData(
        name="Полоса препятствий",
        world_w=world_w,
        spawn=(40.0, float(H - 40 - ph_)),
        platforms=p,
        spikes=s,
        coins=c,
        powerups=powerups,
        saws=saws,
        turrets=turrets,
        goal=goal,
        bg_top=(30, 40, 55),
        bg_bottom=(60, 70, 90),
        plat_color=(60, 70, 90),
        plat_top_color=(120, 140, 165),
    )


LEVELS: list[Callable[[], LevelData]] = [
    level_1, level_2, level_3, level_4, level_5,
]


class Player:
    def __init__(self, x: float, y: float) -> None:
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.w = Feel.PLAYER_W
        self.h = Feel.PLAYER_H
        self.on_ground = False
        self.coyote_timer = 0.0
        self.jump_buffer_timer = 0.0
        self.jump_held = False
        self.facing = 1
        self.dead = False
        self.was_on_ground = False
        self.portal_cooldown = 0.0
        self.gravity_dir = 1  # 1 = вниз (обычно), -1 = вверх (ходьба по потолку)
        self.flip_held = False
        self.low_grav_timer = 0.0  # >0 — гравитация уменьшена вдвое
        # визуальное состояние анимации (физику не затрагивает)
        self.anim_state = "idle"
        self.frame_index = 0
        self.anim_timer = 0.0
        self.anim_step = 1  # ping-pong для idle (+1 вперёд, −1 назад)
        self.facing_right = True
        self.death_cause: str | None = None
        self.death_anim_done = False

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x), int(self.y), int(self.w), int(self.h))

    def reset(self, x: float, y: float) -> None:
        self.__init__(x, y)


class Camera:
    def __init__(self, world_w: int, world_h: int = H) -> None:
        self.world_w = world_w
        self.world_h = world_h
        self.x = 0.0
        self.y = 0.0

    def _clamp_y(self, value: float) -> float:
        # если уровень не выше экрана — вертикального скролла нет (как раньше)
        if self.world_h <= H:
            return 0.0
        return max(0.0, min(value, float(self.world_h - H)))

    def update(self, target_x: float, target_y: float | None = None) -> None:
        # мягкое следование: камера чуть впереди персонажа
        desired = target_x - W * 0.35
        desired = max(0.0, min(desired, float(self.world_w - W)))
        self.x += (desired - self.x) * 0.12
        if target_y is not None:
            desired_y = self._clamp_y(target_y - H * 0.5)
            self.y += (desired_y - self.y) * 0.12

    def snap(self, target_x: float, target_y: float | None = None) -> None:
        self.x = max(0.0, min(target_x - W * 0.35, float(self.world_w - W)))
        if target_y is not None:
            self.y = self._clamp_y(target_y - H * 0.5)

    def apply(self, r: pygame.Rect) -> pygame.Rect:
        return pygame.Rect(r.x - int(self.x), r.y - int(self.y), r.w, r.h)


def circle_rect_hit(cx: float, cy: float, r: float, rect: pygame.Rect) -> bool:
    """Пересечение круга (cx, cy, r) с прямоугольником."""
    nx = max(rect.left, min(cx, rect.right))
    ny = max(rect.top, min(cy, rect.bottom))
    return (cx - nx) ** 2 + (cy - ny) ** 2 <= r * r


# --- scancode-группы для движения (физические клавиши, любая раскладка) ---
SC_LEFT = (pygame.KSCAN_LEFT, pygame.KSCAN_A)
SC_RIGHT = (pygame.KSCAN_RIGHT, pygame.KSCAN_D)
SC_JUMP = (pygame.KSCAN_SPACE, pygame.KSCAN_W, pygame.KSCAN_UP)
SC_FLIP = (pygame.KSCAN_G, pygame.KSCAN_LSHIFT, pygame.KSCAN_RSHIFT)
SC_INTERACT = (pygame.KSCAN_F,)


def evt_is(event: pygame.event.Event, scancodes: tuple[int, ...],
           keycodes: tuple[int, ...] = ()) -> bool:
    """Совпадение KEYDOWN-события по scancode (раскладко-независимо) или keycode."""
    sc = getattr(event, "scancode", None)
    if sc is not None and sc in scancodes:
        return True
    return event.key in keycodes


def evt_number(event: pygame.event.Event) -> int | None:
    """Цифра 1..9 из ряда (через scancode, иначе keycode). Возвращает индекс 0..8."""
    sc = getattr(event, "scancode", None)
    if sc is not None and pygame.KSCAN_1 <= sc <= pygame.KSCAN_9:
        return sc - pygame.KSCAN_1
    if pygame.K_1 <= event.key <= pygame.K_9:
        return event.key - pygame.K_1
    return None


class PlatformerGame:
    def __init__(self) -> None:
        if not pygame.get_init():
            pygame.init()
        pygame.display.set_caption("Платформер")
        self.screen = pygame.display.set_mode((W, H))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("arial", 22)
        self.font_big = pygame.font.SysFont("arial", 36, bold=True)
        self.font_small = pygame.font.SysFont("arial", 18)

        self.state = GameState.LEVEL_SELECT
        self.level_index = 0
        self.selected_index = 0
        self.completed: set[int] = set()
        self.near_button = False
        self.menu_items: list[dict] = []
        # физически нажатые клавиши по scancode — не зависит от раскладки (RU/EN)
        self.held_scancodes: set[int] = set()
        self._menu_item_rects: list[pygame.Rect] = []
        self.level: LevelData | None = None
        self.player = Player(0, 0)
        self.camera = Camera(W)
        self.coins_total = 0
        self.coins_collected = 0
        self.complete_timer = 0.0
        self.death_timer = 0.0
        self.level_time = 0.0
        self.projectiles: list[Projectile] = []
        self.anim_clock = 0.0
        self._external_level: LevelData | None = None
        # слой ассетов (может отсутствовать → рисуем примитивы)
        self.assets = None
        if _get_asset_manager is not None:
            try:
                self.assets = _get_asset_manager()
            except Exception:  # noqa: BLE001
                self.assets = None

    def _has_sprites(self) -> bool:
        return self.assets is not None and getattr(self.assets, "available", False)

    def _held(self, *scancodes: int) -> bool:
        """Зажата ли любая из физических клавиш (scancode). Раскладко-независимо."""
        return any(s in self.held_scancodes for s in scancodes)

    def load_level(self, index: int) -> None:
        self.level_index = index
        self._start_level(LEVELS[index]())

    def play_level_data(self, level: LevelData) -> None:
        """Запустить произвольный LevelData (например, из JSON или редактора)."""
        self.level_index = -1
        self._external_level = level
        self._start_level(level)

    def _start_level(self, level: LevelData) -> None:
        self.level = level
        self.player.reset(*self.level.spawn)
        self.camera = Camera(self.level.world_w, getattr(self.level, "world_h", H))
        self.camera.snap(self.player.x + self.player.w / 2, self.player.y + self.player.h / 2)
        self.coins_total = sum(1 for c in self.level.coins if not c.collected)
        self.coins_collected = 0
        for coin in self.level.coins:
            coin.collected = False
        for en in self.level.enemies:
            en.direction = 1
        self.state = GameState.PLAYING
        self.complete_timer = 0.0
        self.death_timer = 0.0
        self.level_time = 0.0
        self.projectiles = []

    # ---------- меню выбора уровня (встроенные + JSON + редактор) ----------
    def _refresh_menu_items(self) -> None:
        items: list[dict] = []
        for i in range(len(LEVELS)):
            items.append({"kind": "builtin", "index": i, "label": LEVELS[i]().name})
        # пользовательские уровни из levels/*.json
        try:
            from src.levels import level_io

            for p in sorted(level_io.LEVELS_DIR.glob("*.json")):
                if p.name.startswith("_"):
                    continue  # служебные (например, _editor_test_level.json)
                items.append({"kind": "json", "path": str(p), "label": f"[JSON] {p.stem}"})
        except Exception:  # noqa: BLE001
            pass
        items.append({"kind": "editor", "label": "[ Открыть редактор уровней ]"})
        self.menu_items = items
        if self.selected_index >= len(items):
            self.selected_index = len(items) - 1

    def _activate_menu_item(self, idx: int) -> None:
        if not self.menu_items:
            self._refresh_menu_items()
        if not (0 <= idx < len(self.menu_items)):
            return
        item = self.menu_items[idx]
        if item["kind"] == "builtin":
            self.load_level(item["index"])
        elif item["kind"] == "json":
            self._play_json(item["path"])
        elif item["kind"] == "editor":
            self.launch_editor()

    def _menu_hover(self, pos: tuple[int, int]) -> None:
        for i, r in enumerate(self._menu_item_rects):
            if r.collidepoint(pos):
                self.selected_index = i
                return

    def _menu_click(self, pos: tuple[int, int]) -> None:
        for i, r in enumerate(self._menu_item_rects):
            if r.collidepoint(pos):
                self.selected_index = i
                self._activate_menu_item(i)
                return

    def _play_json(self, path: str) -> None:
        from src.levels import level_io

        try:
            level = level_io.dict_to_leveldata(level_io.load_level_file(path))
        except ValueError as e:
            print(f"[level] Ошибка загрузки уровня: {e}")
            return
        self.play_level_data(level)

    def launch_editor(self) -> None:
        """Открыть встроенный редактор и вернуться в меню по выходу из него."""
        try:
            from src.editor.level_editor import run_editor
        except Exception as e:  # noqa: BLE001
            print(f"[editor] Редактор недоступен: {e}")
            return
        run_editor()
        # редактор менял режим дисплея — восстановим окно игры
        self.screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption("Платформер")
        self.held_scancodes.clear()
        self.state = GameState.LEVEL_SELECT
        self._refresh_menu_items()

    def run(self, *, quit_pygame_on_exit: bool = True) -> None:
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            dt = min(dt, 0.05)
            if not self.handle_events():
                break
            self.update(dt)
            self.draw()
            pygame.display.flip()
        if quit_pygame_on_exit:
            pygame.quit()
            sys.exit(0)

    def handle_events(self) -> bool:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYUP:
                self.held_scancodes.discard(getattr(event, "scancode", -1))
                continue
            if event.type == pygame.MOUSEMOTION and self.state == GameState.LEVEL_SELECT:
                self._menu_hover(event.pos)
                continue
            if event.type == pygame.MOUSEBUTTONDOWN and self.state == GameState.LEVEL_SELECT:
                if event.button == 1:
                    self._menu_click(event.pos)
                continue
            if event.type == pygame.KEYDOWN:
                self.held_scancodes.add(getattr(event, "scancode", -1))
                if evt_is(event, (pygame.KSCAN_ESCAPE,), (pygame.K_ESCAPE,)):
                    if self.state == GameState.LEVEL_SELECT:
                        return False
                    self.state = GameState.LEVEL_SELECT
                    continue
                if self.state == GameState.LEVEL_SELECT:
                    self._refresh_menu_items()
                    n = len(self.menu_items)
                    if evt_is(event, (pygame.KSCAN_UP, pygame.KSCAN_W), (pygame.K_UP, pygame.K_w)):
                        self.selected_index = (self.selected_index - 1) % n
                    elif evt_is(event, (pygame.KSCAN_DOWN, pygame.KSCAN_S), (pygame.K_DOWN, pygame.K_s)):
                        self.selected_index = (self.selected_index + 1) % n
                    elif evt_is(event, (pygame.KSCAN_RETURN, pygame.KSCAN_SPACE),
                                (pygame.K_RETURN, pygame.K_SPACE)):
                        self._activate_menu_item(self.selected_index)
                    elif evt_is(event, (pygame.KSCAN_E,), (pygame.K_e,)):
                        self.launch_editor()
                    else:
                        num = evt_number(event)
                        if num is not None and num < n:
                            self.selected_index = num
                            self._activate_menu_item(num)
                elif self.state in (GameState.LEVEL_COMPLETE, GameState.WIN, GameState.DEAD):
                    if evt_is(event, (pygame.KSCAN_RETURN, pygame.KSCAN_SPACE, pygame.KSCAN_R),
                              (pygame.K_RETURN, pygame.K_SPACE, pygame.K_r)):
                        if self.state == GameState.DEAD:
                            if self.level_index < 0 and self._external_level is not None:
                                self.play_level_data(self._external_level)
                            else:
                                self.load_level(self.level_index)
                        else:
                            # после прохождения уровня — обратно в список уровней
                            self.selected_index = min(
                                self.level_index + 1, len(LEVELS) - 1
                            )
                            self.state = GameState.LEVEL_SELECT
        return True

    def update(self, dt: float) -> None:
        if self.state == GameState.LEVEL_SELECT:
            return
        if self.state == GameState.PLAYING:
            self.update_playing(dt)
        elif self.state == GameState.LEVEL_COMPLETE:
            self.complete_timer += dt
            if self.complete_timer > 0.4:
                pass
        elif self.state == GameState.DEAD:
            if (
                self.level is not None
                and self.player.death_cause == "saw"
                and not self.player.death_anim_done
            ):
                self._update_death_anim(dt)
            self.death_timer += dt

    def update_playing(self, dt: float) -> None:
        assert self.level is not None
        p = self.player
        p.portal_cooldown = max(0.0, p.portal_cooldown - dt)
        p.low_grav_timer = max(0.0, p.low_grav_timer - dt)
        self.level_time += dt

        # --- горизонтальное движение (стрелки/WASD/русская раскладка через scancode) ---
        left = self._held(*SC_LEFT)
        right = self._held(*SC_RIGHT)
        want = (-1 if left else 0) + (1 if right else 0)

        accel = Feel.GROUND_ACCEL if p.on_ground else Feel.AIR_ACCEL
        friction = Feel.GROUND_FRICTION if p.on_ground else Feel.AIR_FRICTION

        if want != 0:
            p.vx += want * accel
            p.facing = want
        else:
            p.vx *= friction

        p.vx = max(-Feel.MOVE_SPEED, min(Feel.MOVE_SPEED, p.vx))

        # --- переворот гравитации: G / Shift, стоя на поверхности ---
        g = p.gravity_dir
        flip_pressed = self._held(*SC_FLIP)
        if flip_pressed and not p.flip_held and p.on_ground:
            p.gravity_dir = -g
            g = p.gravity_dir
            p.vy = 0.0
            p.on_ground = False
            p.coyote_timer = 0.0
        p.flip_held = flip_pressed

        # --- прыжок: буфер, coyote time, variable height (с учётом направления g) ---
        jump_pressed = self._held(*SC_JUMP)
        rising = p.vy * g < 0  # движется против гравитации = взлетает
        if jump_pressed:
            p.jump_buffer_timer = Feel.JUMP_BUFFER
        else:
            if p.jump_held and rising:
                p.vy *= Feel.JUMP_CUT_MULT
            p.jump_held = False

        p.jump_buffer_timer = max(0.0, p.jump_buffer_timer - dt)
        if p.on_ground:
            p.coyote_timer = Feel.COYOTE_TIME
        else:
            p.coyote_timer = max(0.0, p.coyote_timer - dt)

        can_jump = p.coyote_timer > 0
        if p.jump_buffer_timer > 0 and can_jump:
            p.vy = Feel.JUMP_VELOCITY * g  # импульс против гравитации
            p.jump_buffer_timer = 0.0
            p.coyote_timer = 0.0
            p.on_ground = False
            p.jump_held = True

        if jump_pressed:
            p.jump_held = True

        # --- гравитация (по текущему направлению; паверап уменьшает вдвое) ---
        # На земле не накапливаем микро-vy — иначе каждый кадр «отлипаем» от пола.
        if p.on_ground and p.vy * g >= 0:
            p.vy = 0.0
        else:
            grav = Feel.GRAVITY
            if p.low_grav_timer > 0:
                grav *= 0.5
            if p.vy * g > 0:  # падение по направлению гравитации — усиливаем дугу
                grav *= Feel.FALL_GRAVITY_MULT
            p.vy += grav * g
            p.vy = max(-Feel.MAX_FALL, min(Feel.MAX_FALL, p.vy))

        # --- интеграция + коллизии ---
        self.move_axis(p, p.vx, "x")
        self.move_axis(p, p.vy, "y")
        self._resolve_ground_contact(p)

        # падение в бездну (в любую сторону при перевёрнутой гравитации)
        world_h = getattr(self.level, "world_h", H)
        if p.y > world_h + 80 or p.y + p.h < -80:
            self.kill_player()

        self.camera.update(p.x + p.w / 2, p.y + p.h / 2)

        # монеты
        pr = p.rect
        for coin in self.level.coins:
            if coin.collected:
                continue
            cr = pygame.Rect(
                int(coin.x - coin.radius),
                int(coin.y - coin.radius),
                int(coin.radius * 2),
                int(coin.radius * 2),
            )
            if pr.colliderect(cr):
                coin.collected = True
                self.coins_collected += 1

        # кнопка: рядом и нажата F → открыть все ворота уровня
        self.near_button = False
        for button in self.level.buttons:
            if pr.colliderect(button.rect.inflate(18, 18)):
                self.near_button = True
                if self._held(*SC_INTERACT):
                    button.pressed = True
                    for gate in self.level.gates:
                        gate.opened = True

        # портал: телепорт в целевую точку (с кулдауном, чтоб не зациклить)
        if p.portal_cooldown <= 0:
            for portal in self.level.portals:
                if pr.colliderect(portal.rect):
                    p.x, p.y = portal.tx, portal.ty
                    p.vx = 0.0
                    p.vy = 0.0
                    p.portal_cooldown = 0.6
                    self.camera.snap(p.x + p.w / 2, p.y + p.h / 2)
                    break

        # паверапы (низкая гравитация)
        for pu in self.level.powerups:
            if pu.collected:
                continue
            if pr.colliderect(pu.rect):
                pu.collected = True
                if pu.kind == "lowgrav":
                    p.low_grav_timer = pu.duration

        # турели: накапливают таймер и выпускают шип-снаряды
        for tu in self.level.turrets:
            tu.timer += dt
            if tu.timer >= tu.interval:
                tu.timer -= tu.interval
                self.projectiles.append(
                    Projectile(tu.x, tu.y, tu.dx * tu.speed, tu.dy * tu.speed)
                )

        # движение снарядов (px/кадр) + отсев за пределами мира
        alive: list[Projectile] = []
        for pj in self.projectiles:
            pj.x += pj.vx
            pj.y += pj.vy
            if -40 <= pj.x <= self.level.world_w + 40 and -80 <= pj.y <= H + 80:
                alive.append(pj)
        self.projectiles = alive

        # смертельные коллизии: шипы, пилы, снаряды
        for spike in (*self.level.spikes, *self.level.spikes_down):
            if pr.colliderect(spike.rect):
                self.kill_player()
                return
        for saw in self.level.saws:
            cx, cy = saw.pos(self.level_time)
            if circle_rect_hit(cx, cy, saw.r * 0.82, pr):
                self.kill_player(cause="saw")
                return
        for pj in self.projectiles:
            if circle_rect_hit(pj.x, pj.y, pj.r, pr):
                self.kill_player()
                return

        # враги: патруль по X между границами + летальный контакт
        for en in self.level.enemies:
            if en.patrol_right > en.patrol_left:
                en.x += en.speed * en.direction
                if en.x <= en.patrol_left:
                    en.x = en.patrol_left
                    en.direction = 1
                elif en.x + en.w >= en.patrol_right:
                    en.x = en.patrol_right - en.w
                    en.direction = -1
            if pr.colliderect(en.rect):
                self.kill_player()
                return

        # анимация игрока (визуал)
        self._update_player_anim(dt, moving=want != 0)

        # цель
        if self.level.goal and pr.colliderect(self.level.goal.rect):
            self.completed.add(self.level_index)
            self.state = GameState.LEVEL_COMPLETE
            self.complete_timer = 0.0

    def move_axis(self, p: Player, velocity: float, axis: str) -> None:
        assert self.level is not None
        if velocity == 0:
            return
        if axis == "x":
            p.x += velocity
        else:
            p.y += velocity

        pr = p.rect
        p.on_ground = False

        solids = [plat.rect for plat in self.level.platforms]
        solids.extend(g.rect for g in self.level.gates if not g.opened)
        for pl in solids:
            if not pr.colliderect(pl):
                continue
            if axis == "x":
                if velocity > 0:
                    p.x = pl.left - p.w
                elif velocity < 0:
                    p.x = pl.right
                pr = p.rect
            else:
                if velocity > 0:  # движение вниз по экрану → упор в верх платформы
                    p.y = pl.top - p.h
                    p.vy = 0
                    if p.gravity_dir > 0:
                        p.on_ground = True
                elif velocity < 0:  # движение вверх → упор в низ платформы (потолок)
                    p.y = pl.bottom
                    p.vy = 0
                    if p.gravity_dir < 0:
                        p.on_ground = True
                pr = p.rect

        # границы мира
        if p.x < 0:
            p.x = 0
        if p.x + p.w > self.level.world_w:
            p.x = self.level.world_w - p.w

    def _resolve_ground_contact(self, p: Player) -> None:
        """Привязка к полу/потолку с допуском — стабильный on_ground без дрожания."""
        assert self.level is not None
        solids = [plat.rect for plat in self.level.platforms]
        solids.extend(g.rect for g in self.level.gates if not g.opened)
        pr = p.rect
        g = p.gravity_dir

        if g > 0:
            landed = False
            for pl in solids:
                if (
                    pr.right > pl.left
                    and pr.left < pl.right
                    and pr.top < pl.bottom
                    and pl.top - GROUND_SNAP <= pr.bottom <= pl.top + GROUND_SNAP
                ):
                    p.y = pl.top - p.h
                    landed = True
                    break
            p.on_ground = landed
            if landed and p.vy > 0:
                p.vy = 0.0
            return

        # гравитация вверх — «пол» на потолке
        on_ceiling = False
        for pl in solids:
            if (
                pr.right > pl.left
                and pr.left < pl.right
                and pr.bottom > pl.top
                and pl.bottom - GROUND_SNAP <= pr.top <= pl.bottom + GROUND_SNAP
            ):
                p.y = pl.bottom
                on_ceiling = True
                break
        p.on_ground = on_ceiling
        if on_ceiling and p.vy < 0:
            p.vy = 0.0

    def kill_player(self, cause: str | None = None) -> None:
        p = self.player
        p.dead = True
        p.death_cause = cause
        p.death_anim_done = False
        if cause == "saw":
            p.vx = 0.0
            p.vy = 0.0
            p.anim_state = "death"
            p.frame_index = 0
            p.anim_timer = 0.0
        self.state = GameState.DEAD
        self.death_timer = 0.0

    def _update_death_anim(self, dt: float) -> None:
        p = self.player
        skin = getattr(self.level, "player_asset_set", DEFAULT_PLAYER_SKIN)
        if self.assets is not None:
            n = len(self.assets.player_frames("death", skin=skin))
        else:
            n = PLAYER_ANIM_FRAME_COUNTS["death"]
        p.anim_timer += dt
        duration = self._frame_duration("death", p.frame_index)
        if p.anim_timer < duration:
            return
        p.anim_timer -= duration
        if p.frame_index < n - 1:
            p.frame_index += 1
        else:
            p.death_anim_done = True

    def _frame_duration(self, state: str, frame_index: int) -> float:
        durs = PLAYER_ANIM_DURATIONS.get(state)
        if not durs:
            return PLAYER_ANIM_DEFAULT_DURATION
        return durs[frame_index % len(durs)]

    def _advance_anim_frame(self, p: Player) -> None:
        n = PLAYER_ANIM_FRAME_COUNTS.get(p.anim_state, 4)
        if p.anim_state == "death":
            if p.frame_index < n - 1:
                p.frame_index += 1
            return
        if p.anim_state == "idle" and n > 1:
            nxt = p.frame_index + p.anim_step
            if nxt >= n - 1:
                p.frame_index = n - 1
                p.anim_step = -1
            elif nxt <= 0:
                p.frame_index = 0
                p.anim_step = 1
            else:
                p.frame_index = nxt
        else:
            p.frame_index = (p.frame_index + 1) % max(1, n)

    def _update_player_anim(self, dt: float, *, moving: bool) -> None:
        p = self.player
        if abs(p.vx) > 0.3:
            p.facing_right = p.vx > 0
        g = p.gravity_dir
        if p.on_ground:
            new_state = "run" if moving and abs(p.vx) > 0.15 else "idle"
        else:
            rising = p.vy * g < -0.5
            falling = p.vy * g > 0.5
            if rising:
                new_state = "jump"
            elif falling:
                new_state = "fall"
            else:
                new_state = "jump"
        if new_state != p.anim_state:
            p.anim_state = new_state
            p.frame_index = 0
            p.anim_timer = 0.0
            p.anim_step = 1
        p.anim_timer += dt
        duration = self._frame_duration(p.anim_state, p.frame_index)
        if p.anim_timer >= duration:
            p.anim_timer -= duration
            self._advance_anim_frame(p)

    def draw(self) -> None:
        if self.state == GameState.LEVEL_SELECT:
            self.draw_level_select()
            return

        assert self.level is not None
        # фон: спрайт (если есть) либо градиент-полосы
        bg_drawn = False
        if self._has_sprites() and self.level.background:
            try:
                bg = self.assets.background(self.level.background)
                bg = self.assets.scaled(bg, (W, H))
                self.screen.blit(bg, (0, 0))
                bg_drawn = True
            except Exception:  # noqa: BLE001
                bg_drawn = False
        if not bg_drawn:
            for i in range(H):
                t = i / H
                c = tuple(
                    int(self.level.bg_top[j] * (1 - t) + self.level.bg_bottom[j] * t)
                    for j in range(3)
                )
                pygame.draw.line(self.screen, c, (0, i), (W, i))

        cam_x = int(self.camera.x)
        cam_y = int(self.camera.y)
        use_sprites = self._has_sprites()

        # платформы: тайлим спрайт по сетке, иначе прямоугольник
        for plat in self.level.platforms:
            r = self.camera.apply(plat.rect)
            if r.right < 0 or r.left > W:
                continue
            if use_sprites:
                self._blit_tiled(self.assets.tile(plat.tile_id), r)
            else:
                pygame.draw.rect(self.screen, self.level.plat_color, r)
                top = pygame.Rect(r.x, r.y, r.w, 4)
                pygame.draw.rect(self.screen, self.level.plat_top_color, top)
            if DEBUG_DRAW_HITBOXES:
                pygame.draw.rect(self.screen, (255, 0, 0), r, 1)

        # шипы остриём вверх — на полу
        for spike in self.level.spikes:
            r = self.camera.apply(spike.rect)
            if r.right < 0 or r.left > W:
                continue
            if use_sprites:
                self._blit_tiled(self.assets.obstacle("spikes"), r)
            else:
                self.draw_spikes(r)
            if DEBUG_DRAW_HITBOXES:
                pygame.draw.rect(self.screen, (255, 0, 0), r, 1)

        # шипы остриём вниз — на потолке
        for spike in self.level.spikes_down:
            r = self.camera.apply(spike.rect)
            if r.right < 0 or r.left > W:
                continue
            if use_sprites:
                spr = pygame.transform.flip(self.assets.obstacle("spikes"), False, True)
                self._blit_tiled(spr, r)
            else:
                self.draw_spikes(r, down=True)
            if DEBUG_DRAW_HITBOXES:
                pygame.draw.rect(self.screen, (255, 0, 0), r, 1)

        # ворота
        for gate in self.level.gates:
            r = self.camera.apply(gate.rect)
            if r.right < 0 or r.left > W:
                continue
            if gate.opened:
                pygame.draw.rect(self.screen, GATE_FRAME, r, 2)
            else:
                pygame.draw.rect(self.screen, GATE_CLOSED, r)
                for by in range(r.top, r.bottom, 18):
                    pygame.draw.line(
                        self.screen, GATE_FRAME, (r.left, by), (r.right, by), 2
                    )
                pygame.draw.rect(self.screen, GATE_FRAME, r, 3)

        # кнопки
        for button in self.level.buttons:
            r = self.camera.apply(button.rect)
            if r.right < 0 or r.left > W:
                continue
            color = BUTTON_DOWN if button.pressed else BUTTON_UP
            base = pygame.Rect(r.x, r.y + r.h - 6, r.w, 6)
            pygame.draw.rect(self.screen, (40, 40, 50), base, border_radius=2)
            top = pygame.Rect(r.x + 4, r.y + (6 if button.pressed else 0), r.w - 8, r.h - 6)
            pygame.draw.rect(self.screen, color, top, border_radius=3)

        # порталы (пульсирующие)
        pt = pygame.time.get_ticks() / 250.0
        for portal in self.level.portals:
            r = self.camera.apply(portal.rect)
            if r.right < 0 or r.left > W:
                continue
            pulse = int(3 * (1 + math.sin(pt)))
            pygame.draw.ellipse(self.screen, PORTAL, r.inflate(pulse, pulse))
            pygame.draw.ellipse(self.screen, PORTAL_CORE, r.inflate(-r.w // 3, -r.h // 3))

        # монеты: анимированный спрайт или круг
        t = pygame.time.get_ticks() / 200.0
        coin_frames = self.assets.coin_frames() if use_sprites else None
        for coin in self.level.coins:
            if coin.collected:
                continue
            sx = int(coin.x - cam_x)
            sy = int(coin.y - cam_y)
            if sx < -20 or sx > W + 20:
                continue
            bob = math.sin(t + coin.x * 0.01) * 3
            if coin_frames:
                fr = coin_frames[int(self.level_time * 8) % len(coin_frames)]
                size = int(coin.radius * 2)
                spr = self.assets.scaled(fr, (size, size))
                self.screen.blit(spr, (sx - size // 2, int(sy + bob) - size // 2))
            else:
                pygame.draw.circle(self.screen, COIN, (sx, int(sy + bob)), int(coin.radius))
                pygame.draw.circle(
                    self.screen, COIN_SHINE, (sx - 3, int(sy + bob - 3)), 4
                )
            if DEBUG_DRAW_HITBOXES:
                cr = pygame.Rect(0, 0, int(coin.radius * 2), int(coin.radius * 2))
                cr.center = (sx, int(sy + bob))
                pygame.draw.rect(self.screen, (255, 0, 0), cr, 1)

        # паверапы (низкая гравитация): пульсирующий орб со стрелкой вниз
        for pu in self.level.powerups:
            if pu.collected:
                continue
            sx = int(pu.x - cam_x)
            sy = int(pu.y - cam_y)
            if sx < -30 or sx > W + 30:
                continue
            pr_ = int(2 * (1 + math.sin(pt)))
            pygame.draw.circle(self.screen, POWERUP, (sx, sy), int(pu.radius) + pr_)
            pygame.draw.circle(self.screen, POWERUP_CORE, (sx, sy), int(pu.radius) - 5)
            pygame.draw.polygon(
                self.screen, POWERUP,
                [(sx - 6, sy - 3), (sx + 6, sy - 3), (sx, sy + 6)],
            )

        # турели (тумбы со стволом по направлению огня)
        for tu in self.level.turrets:
            bx = int(tu.x - cam_x)
            by = int(tu.y - cam_y)
            if bx < -30 or bx > W + 30:
                continue
            pygame.draw.rect(self.screen, TURRET, (bx - 12, by - 12, 24, 24), border_radius=4)
            pygame.draw.rect(
                self.screen, (50, 55, 70),
                (bx + int(tu.dx * 10) - 5, by + int(tu.dy * 10) - 5, 12, 12),
                border_radius=2,
            )

        # снаряды-шипы
        for pj in self.projectiles:
            sx = int(pj.x - cam_x)
            sy = int(pj.y - cam_y)
            if sx < -20 or sx > W + 20:
                continue
            pygame.draw.circle(self.screen, PROJECTILE, (sx, sy), int(pj.r))
            pygame.draw.circle(self.screen, (120, 30, 20), (sx, sy), int(pj.r), 2)

        # вращающиеся пилы
        for saw in self.level.saws:
            cx, cy = saw.pos(self.level_time)
            sx = int(cx - cam_x)
            sy = int(cy - cam_y)
            if sx < -40 or sx > W + 40:
                continue
            r = int(saw.r)
            ang = self.level_time * 9.0  # скорость вращения зубьев
            pygame.draw.circle(self.screen, SAW, (sx, sy), r)
            for i in range(12):
                a = ang + i * (2 * math.pi / 12)
                tx = sx + int(math.cos(a) * (r + 6))
                ty = sy + int(math.sin(a) * (r + 6))
                pygame.draw.line(self.screen, SAW, (sx, sy), (tx, ty), 3)
            pygame.draw.circle(self.screen, SAW_CORE, (sx, sy), max(3, r // 3))

        # враги (слаймы): спрайт или прямоугольник
        for en in self.level.enemies:
            er = self.camera.apply(en.rect)
            if er.right < 0 or er.left > W:
                continue
            if use_sprites:
                frames = self.assets.enemy_frames(en.asset_id, "idle")
                fr = frames[int(self.level_time * 4) % len(frames)]
                spr = self.assets.scaled(fr, (er.w, er.h))
                if en.direction < 0:
                    spr = pygame.transform.flip(spr, True, False)
                self.screen.blit(spr, er.topleft)
            else:
                pygame.draw.rect(self.screen, (90, 200, 110), er, border_radius=6)
                pygame.draw.rect(self.screen, (60, 160, 80), er, 2, border_radius=6)
            if DEBUG_DRAW_HITBOXES:
                pygame.draw.rect(self.screen, (255, 0, 0), er, 1)

        # цель: флаг-спрайт или зелёный прямоугольник EXIT
        if self.level.goal:
            gr = self.camera.apply(self.level.goal.rect)
            flag_drawn = False
            if use_sprites:
                try:
                    spr = self.assets.scaled(self.assets.item("flag"), (gr.w, gr.h))
                    self.screen.blit(spr, gr.topleft)
                    flag_drawn = True
                except Exception:  # noqa: BLE001
                    flag_drawn = False
            if not flag_drawn:
                pygame.draw.rect(self.screen, GOAL, gr, border_radius=4)
                pygame.draw.rect(self.screen, (60, 200, 100), gr, 3, border_radius=4)
                label = self.font_small.render("EXIT", True, (20, 60, 30))
                self.screen.blit(label, (gr.centerx - label.get_width() // 2, gr.y - 22))
            if DEBUG_DRAW_HITBOXES:
                pygame.draw.rect(self.screen, (255, 0, 0), gr, 1)

        # игрок: спрайт по состоянию анимации, иначе примитив
        gdir = self.player.gravity_dir
        pr = self.camera.apply(self.player.rect)
        if self.player.low_grav_timer > 0:
            aura = pr.inflate(14, 14)
            pygame.draw.ellipse(self.screen, POWERUP, aura, 2)
        player_drawn = False
        if use_sprites:
            try:
                skin = getattr(self.level, "player_asset_set", DEFAULT_PLAYER_SKIN)
                frames = self.assets.player_frames(self.player.anim_state, skin=skin)
                if self.player.anim_state == "death":
                    idx = min(self.player.frame_index, len(frames) - 1)
                else:
                    idx = self.player.frame_index % len(frames)
                fr = frames[idx]
                spr = self.assets.scaled(fr, (pr.w + 8, pr.h + 4))
                if not self.player.facing_right:
                    spr = pygame.transform.flip(spr, True, False)
                if gdir < 0:
                    spr = pygame.transform.flip(spr, False, True)
                self.screen.blit(spr, (pr.x - 4, pr.y - (0 if gdir > 0 else 4)))
                player_drawn = True
            except Exception:  # noqa: BLE001
                player_drawn = False
        if not player_drawn:
            pygame.draw.rect(self.screen, PLAYER_ACCENT, pr.move(0, 4 * gdir))
            body = pr.inflate(-4, -8)
            pygame.draw.rect(self.screen, PLAYER, body, border_radius=6)
            eye_x = body.right - 8 if self.player.facing > 0 else body.left + 4
            eye_y = body.y + 10 if gdir > 0 else body.bottom - 10
            pygame.draw.circle(self.screen, UI, (eye_x, eye_y), 4)
        if DEBUG_DRAW_HITBOXES:
            pygame.draw.rect(self.screen, (255, 0, 0), pr, 1)

        # HUD
        self.draw_hud()

        if self.state == GameState.LEVEL_COMPLETE:
            self.draw_overlay(
                "Уровень пройден!",
                f"Монеты: {self.coins_collected}/{self.coins_total}",
                "Enter — к списку уровней",
            )
        elif self.state == GameState.DEAD:
            if self.player.death_anim_done or self.player.death_cause != "saw":
                self.draw_overlay("Вы погибли", "", "R / Enter — заново")

    def draw_hud(self) -> None:
        assert self.level is not None
        title = self.font.render(
            f"{self.level.name}  |  Монеты: {self.coins_collected}/{self.coins_total}",
            True,
            UI,
        )
        self.screen.blit(title, (12, 10))
        has_gravity = bool(self.level.spikes_down) or self.player.gravity_dir < 0
        base_hint = "← → / A D — бег   Space / W / ↑ — прыжок   Esc — список уровней"
        if has_gravity:
            base_hint = (
                "← → / A D — бег   Space / W — прыжок   G / Shift — гравитация   Esc — меню"
            )
        hints = self.font_small.render(base_hint, True, UI_DIM)
        self.screen.blit(hints, (12, H - 28))

        # индикатор направления гравитации
        if has_gravity:
            up = self.player.gravity_dir < 0
            arrow = "Гравитация: ↑ ПОТОЛОК" if up else "Гравитация: ↓ ПОЛ"
            ind = self.font_small.render(arrow, True, GRAV_ACCENT)
            self.screen.blit(ind, (W - ind.get_width() - 12, 12))

        # таймер низкой гравитации (паверап)
        if self.player.low_grav_timer > 0:
            secs = self.player.low_grav_timer
            label = self.font.render(
                f"Низкая гравитация: {secs:0.1f}s", True, POWERUP_CORE
            )
            bx, by = 12, 40
            self.screen.blit(label, (bx, by))
            frac = max(0.0, min(1.0, secs / 30.0))
            bar_w = 220
            pygame.draw.rect(self.screen, (30, 40, 55), (bx, by + 28, bar_w, 10), border_radius=4)
            pygame.draw.rect(
                self.screen, POWERUP, (bx, by + 28, int(bar_w * frac), 10), border_radius=4
            )

        # подсказка при нахождении рядом с кнопкой
        if self.near_button:
            prompt = self.font.render("Нажмите F", True, (255, 240, 120))
            self.screen.blit(
                prompt, (W // 2 - prompt.get_width() // 2, H - 70)
            )

    def draw_level_select(self) -> None:
        # фон-градиент
        for i in range(H):
            tt = i / H
            c = tuple(int(SKY[j] * (1 - tt) + (60, 90, 140)[j] * tt) for j in range(3))
            pygame.draw.line(self.screen, c, (0, i), (W, i))

        title = self.font_big.render("Выбор уровня", True, UI)
        self.screen.blit(title, (W // 2 - title.get_width() // 2, 36))

        if not self.menu_items:
            self._refresh_menu_items()

        # компактный шаг, чтобы помещался длинный список (уровни + JSON + редактор)
        n = len(self.menu_items)
        step = 40 if n <= 9 else 32
        y = 110
        self._menu_item_rects = []
        row_w = 460
        for i, item in enumerate(self.menu_items):
            selected = i == self.selected_index
            label = item["label"]
            if item["kind"] == "builtin" and item["index"] in self.completed:
                label += "  ✓"
            prefix = f"{i + 1}. " if i < 9 else "   "
            if item["kind"] == "editor":
                base_color = (140, 255, 180)
            elif item["kind"] == "json":
                base_color = (180, 210, 255)
            else:
                base_color = UI_DIM
            color = (255, 240, 140) if selected else base_color
            # кликабельная строка (мышь)
            row = pygame.Rect(W // 2 - row_w // 2, y - 4, row_w, step - 4)
            self._menu_item_rects.append(row)
            if selected:
                pygame.draw.rect(self.screen, (50, 70, 110), row, border_radius=6)
                pygame.draw.rect(self.screen, (255, 255, 255), row, 2, border_radius=6)
            surf = self.font.render(prefix + label, True, color)
            self.screen.blit(surf, (W // 2 - surf.get_width() // 2, y))
            y += step

        hints = [
            "Мышь: наведи и кликни    ↑↓/WS — выбор    Enter — играть/открыть",
            "1–9 — быстрый выбор    E — редактор    Esc — в главное меню",
        ]
        hy = max(y + 16, H - 64)
        for line in hints:
            surf = self.font_small.render(line, True, (225, 230, 245))
            self.screen.blit(surf, (W // 2 - surf.get_width() // 2, hy))
            hy += 24

    def _blit_tiled(self, sprite: pygame.Surface, r: pygame.Rect) -> None:
        """Замостить прямоугольник r спрайтом-тайлом по сетке (визуал)."""
        assert self.assets is not None
        step = max(8, min(r.w, r.h)) if (r.w <= 24 or r.h <= 24) else 48
        # для тонких полос (платформы/шипы) тайлим по короткой стороне
        tw = th = max(16, min(48, step))
        tile = self.assets.scaled(sprite, (tw, th))
        prev_clip = self.screen.get_clip()
        self.screen.set_clip(r)
        y = r.y
        while y < r.bottom:
            x = r.x
            while x < r.right:
                self.screen.blit(tile, (x, y))
                x += tw
            y += th
        self.screen.set_clip(prev_clip)

    def draw_spikes(self, r: pygame.Rect, down: bool = False) -> None:
        n = max(1, r.w // 14)
        w = r.w / n
        for i in range(n):
            x0 = r.x + i * w
            if down:  # остриём вниз (на потолке)
                pts = [(x0, r.top), (x0 + w / 2, r.bottom), (x0 + w, r.top)]
            else:  # остриём вверх (на полу)
                pts = [(x0, r.bottom), (x0 + w / 2, r.top), (x0 + w, r.bottom)]
            pygame.draw.polygon(self.screen, SPIKE, pts)

    def draw_overlay(self, title: str, sub: str, hint: str) -> None:
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        self.screen.blit(overlay, (0, 0))
        t = self.font_big.render(title, True, UI)
        self.screen.blit(t, (W // 2 - t.get_width() // 2, H // 2 - 50))
        if sub:
            s = self.font.render(sub, True, UI_DIM)
            self.screen.blit(s, (W // 2 - s.get_width() // 2, H // 2))
        h = self.font_small.render(hint, True, UI)
        self.screen.blit(h, (W // 2 - h.get_width() // 2, H // 2 + 45))


def run_platformer_session(
    *,
    restore_size: tuple[int, int] | None = None,
    restore_caption: str | None = None,
) -> None:
    """Запуск платформера; при restore_size — вернуть экран (для вложенного меню)."""
    game = PlatformerGame()
    try:
        game.run(quit_pygame_on_exit=restore_size is None)
    finally:
        if restore_size is not None:
            pygame.display.set_mode(restore_size)
            if restore_caption:
                pygame.display.set_caption(restore_caption)


def run_level_file(level_path: str, player_skin: str | None = None) -> None:
    """Запустить игру сразу в уровне из JSON-файла (--level)."""
    from src.levels import level_io

    game = PlatformerGame()
    try:
        level = level_io.dict_to_leveldata(level_io.load_level_file(level_path))
        if player_skin:
            level.player_asset_set = player_skin
        game.play_level_data(level)
    except ValueError as e:
        print(f"[level] Ошибка загрузки уровня: {e}")
        print("[level] Запускаю меню выбора уровней.")
    game.run()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Pygame платформер")
    parser.add_argument("--editor", action="store_true", help="запустить редактор уровней")
    parser.add_argument("--level", metavar="PATH", help="запустить уровень из JSON")
    parser.add_argument(
        "--skin",
        metavar="ID",
        help="скин игрока (default_player, pink_monster, owlet_monster, dude_monster)",
    )
    parser.add_argument("--debug-hitboxes", action="store_true", help="показывать хитбоксы")
    args = parser.parse_args()

    if args.debug_hitboxes:
        global DEBUG_DRAW_HITBOXES
        DEBUG_DRAW_HITBOXES = True

    if args.editor:
        from src.editor.level_editor import run_editor

        run_editor()
        return
    if args.level:
        run_level_file(args.level, player_skin=args.skin)
        return
    run_platformer_session()


if __name__ == "__main__":
    main()
