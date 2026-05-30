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


@dataclass
class RectObj:
    x: float
    y: float
    w: float
    h: float

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
class LevelData:
    name: str
    world_w: int
    spawn: tuple[float, float]
    platforms: list[RectObj] = field(default_factory=list)
    spikes: list[RectObj] = field(default_factory=list)
    coins: list[CoinObj] = field(default_factory=list)
    portals: list[Portal] = field(default_factory=list)
    buttons: list[Button] = field(default_factory=list)
    gates: list[Gate] = field(default_factory=list)
    goal: RectObj | None = None
    bg_top: tuple[int, int, int] = SKY
    bg_bottom: tuple[int, int, int] = GROUND
    plat_color: tuple[int, int, int] = PLATFORM
    plat_top_color: tuple[int, int, int] = PLATFORM_TOP


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


LEVELS: list[Callable[[], LevelData]] = [level_1, level_2, level_3]


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

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x), int(self.y), int(self.w), int(self.h))

    def reset(self, x: float, y: float) -> None:
        self.__init__(x, y)


class Camera:
    def __init__(self, world_w: int) -> None:
        self.world_w = world_w
        self.x = 0.0

    def update(self, target_x: float) -> None:
        # мягкое следование: камера чуть впереди персонажа
        desired = target_x - W * 0.35
        desired = max(0.0, min(desired, float(self.world_w - W)))
        self.x += (desired - self.x) * 0.12

    def apply(self, r: pygame.Rect) -> pygame.Rect:
        return pygame.Rect(r.x - int(self.x), r.y, r.w, r.h)


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
        self.level: LevelData | None = None
        self.player = Player(0, 0)
        self.camera = Camera(W)
        self.coins_total = 0
        self.coins_collected = 0
        self.complete_timer = 0.0
        self.death_timer = 0.0

    def load_level(self, index: int) -> None:
        self.level_index = index
        self.level = LEVELS[index]()
        self.player.reset(*self.level.spawn)
        self.camera = Camera(self.level.world_w)
        self.coins_total = sum(1 for c in self.level.coins if not c.collected)
        self.coins_collected = 0
        for coin in self.level.coins:
            coin.collected = False
        self.state = GameState.PLAYING
        self.complete_timer = 0.0
        self.death_timer = 0.0

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
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.state == GameState.LEVEL_SELECT:
                        return False
                    self.state = GameState.LEVEL_SELECT
                    continue
                if self.state == GameState.LEVEL_SELECT:
                    if event.key in (pygame.K_UP, pygame.K_w):
                        self.selected_index = (self.selected_index - 1) % len(LEVELS)
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        self.selected_index = (self.selected_index + 1) % len(LEVELS)
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        self.load_level(self.selected_index)
                    elif pygame.K_1 <= event.key <= pygame.K_9:
                        idx = event.key - pygame.K_1
                        if idx < len(LEVELS):
                            self.selected_index = idx
                            self.load_level(idx)
                elif self.state in (GameState.LEVEL_COMPLETE, GameState.WIN, GameState.DEAD):
                    if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_r):
                        if self.state == GameState.DEAD:
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
            self.death_timer += dt

    def update_playing(self, dt: float) -> None:
        assert self.level is not None
        p = self.player
        keys = pygame.key.get_pressed()
        p.portal_cooldown = max(0.0, p.portal_cooldown - dt)

        # --- горизонтальное движение (стрелки и WASD дублируют друг друга) ---
        left = keys[pygame.K_LEFT] or keys[pygame.K_a]
        right = keys[pygame.K_RIGHT] or keys[pygame.K_d]
        want = (-1 if left else 0) + (1 if right else 0)

        accel = Feel.GROUND_ACCEL if p.on_ground else Feel.AIR_ACCEL
        friction = Feel.GROUND_FRICTION if p.on_ground else Feel.AIR_FRICTION

        if want != 0:
            p.vx += want * accel
            p.facing = want
        else:
            p.vx *= friction

        p.vx = max(-Feel.MOVE_SPEED, min(Feel.MOVE_SPEED, p.vx))

        # --- прыжок: буфер, coyote time, variable height ---
        jump_pressed = keys[pygame.K_SPACE] or keys[pygame.K_w] or keys[pygame.K_UP]
        if jump_pressed:
            p.jump_buffer_timer = Feel.JUMP_BUFFER
        else:
            if p.jump_held and p.vy < 0:
                p.vy *= Feel.JUMP_CUT_MULT
            p.jump_held = False

        p.jump_buffer_timer = max(0.0, p.jump_buffer_timer - dt)
        if p.on_ground:
            p.coyote_timer = Feel.COYOTE_TIME
        else:
            p.coyote_timer = max(0.0, p.coyote_timer - dt)

        can_jump = p.coyote_timer > 0
        if p.jump_buffer_timer > 0 and can_jump:
            p.vy = Feel.JUMP_VELOCITY
            p.jump_buffer_timer = 0.0
            p.coyote_timer = 0.0
            p.on_ground = False
            p.jump_held = True

        if jump_pressed:
            p.jump_held = True

        # --- гравитация ---
        grav = Feel.GRAVITY
        if p.vy > 0:
            grav *= Feel.FALL_GRAVITY_MULT
        p.vy += grav
        p.vy = min(p.vy, Feel.MAX_FALL)

        # --- интеграция + коллизии ---
        self.move_axis(p, p.vx, "x")
        self.move_axis(p, p.vy, "y")

        # падение в бездну
        if p.y > H + 80:
            self.kill_player()

        self.camera.update(p.x + p.w / 2)

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
                if keys[pygame.K_f]:
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
                    self.camera.x = max(
                        0.0,
                        min(p.x + p.w / 2 - W * 0.35, float(self.level.world_w - W)),
                    )
                    break

        # шипы
        for spike in self.level.spikes:
            if pr.colliderect(spike.rect):
                self.kill_player()
                return

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
                if velocity > 0:
                    p.y = pl.top - p.h
                    p.vy = 0
                    p.on_ground = True
                elif velocity < 0:
                    p.y = pl.bottom
                    p.vy = 0
                pr = p.rect

        # границы мира
        if p.x < 0:
            p.x = 0
        if p.x + p.w > self.level.world_w:
            p.x = self.level.world_w - p.w

    def kill_player(self) -> None:
        self.player.dead = True
        self.state = GameState.DEAD
        self.death_timer = 0.0

    def draw(self) -> None:
        if self.state == GameState.LEVEL_SELECT:
            self.draw_level_select()
            return

        assert self.level is not None
        # фон с градиентом (полосами)
        for i in range(H):
            t = i / H
            c = tuple(
                int(self.level.bg_top[j] * (1 - t) + self.level.bg_bottom[j] * t)
                for j in range(3)
            )
            pygame.draw.line(self.screen, c, (0, i), (W, i))

        cam_x = int(self.camera.x)

        # платформы
        for plat in self.level.platforms:
            r = self.camera.apply(plat.rect)
            if r.right < 0 or r.left > W:
                continue
            pygame.draw.rect(self.screen, self.level.plat_color, r)
            top = pygame.Rect(r.x, r.y, r.w, 4)
            pygame.draw.rect(self.screen, self.level.plat_top_color, top)

        # шипы (треугольники)
        for spike in self.level.spikes:
            r = self.camera.apply(spike.rect)
            if r.right < 0 or r.left > W:
                continue
            self.draw_spikes(r)

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

        # монеты
        t = pygame.time.get_ticks() / 200.0
        for coin in self.level.coins:
            if coin.collected:
                continue
            sx = int(coin.x - cam_x)
            sy = int(coin.y)
            if sx < -20 or sx > W + 20:
                continue
            bob = math.sin(t + coin.x * 0.01) * 3
            pygame.draw.circle(self.screen, COIN, (sx, int(sy + bob)), int(coin.radius))
            pygame.draw.circle(
                self.screen, COIN_SHINE, (sx - 3, int(sy + bob - 3)), 4
            )

        # цель
        if self.level.goal:
            gr = self.camera.apply(self.level.goal.rect)
            pygame.draw.rect(self.screen, GOAL, gr, border_radius=4)
            pygame.draw.rect(self.screen, (60, 200, 100), gr, 3, border_radius=4)
            label = self.font_small.render("EXIT", True, (20, 60, 30))
            self.screen.blit(label, (gr.centerx - label.get_width() // 2, gr.y - 22))

        # игрок
        pr = self.camera.apply(self.player.rect)
        pygame.draw.rect(self.screen, PLAYER_ACCENT, pr.move(0, 4))
        body = pr.inflate(-4, -8)
        pygame.draw.rect(self.screen, PLAYER, body, border_radius=6)
        eye_x = body.right - 8 if self.player.facing > 0 else body.left + 4
        pygame.draw.circle(self.screen, UI, (eye_x, body.y + 10), 4)

        # HUD
        self.draw_hud()

        if self.state == GameState.LEVEL_COMPLETE:
            self.draw_overlay(
                "Уровень пройден!",
                f"Монеты: {self.coins_collected}/{self.coins_total}",
                "Enter — к списку уровней",
            )
        elif self.state == GameState.DEAD:
            self.draw_overlay("Вы погибли", "", "R / Enter — заново")

    def draw_hud(self) -> None:
        assert self.level is not None
        title = self.font.render(
            f"{self.level.name}  |  Монеты: {self.coins_collected}/{self.coins_total}",
            True,
            UI,
        )
        self.screen.blit(title, (12, 10))
        hints = self.font_small.render(
            "← → / A D — бег   Space / W / ↑ — прыжок   Esc — список уровней",
            True,
            UI_DIM,
        )
        self.screen.blit(hints, (12, H - 28))

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
        self.screen.blit(title, (W // 2 - title.get_width() // 2, 50))

        names = [LEVELS[i]().name for i in range(len(LEVELS))]
        y = 150
        for i, nm in enumerate(names):
            selected = i == self.selected_index
            done = "  ✓" if i in self.completed else ""
            label = f"{i + 1}. {nm}{done}"
            color = (255, 240, 140) if selected else UI_DIM
            surf = self.font.render(label, True, color)
            x = W // 2 - surf.get_width() // 2
            if selected:
                box = pygame.Rect(x - 24, y - 6, surf.get_width() + 48, 34)
                pygame.draw.rect(self.screen, (255, 255, 255), box, 2, border_radius=6)
                marker = self.font.render(">", True, (255, 240, 140))
                self.screen.blit(marker, (x - 24, y))
            self.screen.blit(surf, (x, y))
            y += 48

        hints = [
            "↑ ↓ / W S — выбор    Enter / Space — играть    1–9 — быстрый выбор",
            "Управление в игре: ← → / A D, прыжок Space/W/↑, портал — войти, кнопка — F",
            "Esc — выход в главное меню",
        ]
        hy = y + 30
        for line in hints:
            surf = self.font_small.render(line, True, (225, 230, 245))
            self.screen.blit(surf, (W // 2 - surf.get_width() // 2, hy))
            hy += 26

    def draw_spikes(self, r: pygame.Rect) -> None:
        n = max(1, r.w // 14)
        w = r.w / n
        for i in range(n):
            x0 = r.x + i * w
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


def main() -> None:
    run_platformer_session()


if __name__ == "__main__":
    main()
