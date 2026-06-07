"""
Встроенный редактор уровней на чистом Pygame (без внешних GUI).

Запуск:
    python main.py --editor      (или python platformer.py --editor)

Возможности: палитра ассетов, сетка тайлов и свободные объекты, расстановка
платформ/врагов/предметов/препятствий, старт и конец уровня, изменение
размера, сохранение/загрузка JSON и playtest прямо из редактора.

Управление см. в подсказке на экране и в README.
"""

from __future__ import annotations

import copy
import math
from pathlib import Path

import pygame

from src.assets import asset_loader
from src.assets.asset_registry import (
    BACKGROUND_IDS,
    ENEMY_IDS,
    ITEM_IDS,
    OBSTACLE_IDS,
    TILE_IDS,
    get_asset_manager,
)
from src.levels import level_io

EDITOR_W, EDITOR_H = 1120, 630
PALETTE_W = 200
TOOLBAR_H = 58

BG = (28, 32, 44)
PANEL = (40, 46, 62)
PANEL_HI = (70, 90, 130)
GRID = (60, 66, 84)
TEXT = (230, 235, 245)
TEXT_DIM = (160, 168, 185)
ACCENT = (255, 200, 90)

MODES = {
    pygame.K_1: "tiles",
    pygame.K_2: "platforms",
    pygame.K_3: "enemies",
    pygame.K_4: "items",
    pygame.K_5: "obstacles",
    pygame.K_6: "player_start",
    pygame.K_7: "level_end",
    pygame.K_8: "select",
    pygame.K_9: "background",
    pygame.K_0: "test",
}

MODE_LABELS = {
    "tiles": "1 Tiles",
    "platforms": "2 Platforms",
    "enemies": "3 Enemies",
    "items": "4 Items",
    "obstacles": "5 Obstacles",
    "player_start": "6 Player start",
    "level_end": "7 Level end",
    "select": "8 Select/Delete",
    "background": "9 Background",
    "test": "0 Test",
}

MODE_ORDER = [
    "tiles", "platforms", "enemies", "items", "obstacles",
    "player_start", "level_end", "select", "background", "test",
]

# scancode → режим (физические цифры, работает на любой раскладке)
MODES_SC = {getattr(pygame, f"KSCAN_{(i + 1) % 10}"): m for i, m in enumerate(MODE_ORDER)}

# scancode-группы камеры (раскладко-независимо)
SC_CAM_LEFT = (pygame.KSCAN_A, pygame.KSCAN_LEFT)
SC_CAM_RIGHT = (pygame.KSCAN_D, pygame.KSCAN_RIGHT)
SC_CAM_UP = (pygame.KSCAN_W, pygame.KSCAN_UP)
SC_CAM_DOWN = (pygame.KSCAN_S, pygame.KSCAN_DOWN)


class LevelEditor:
    def __init__(self, level: dict | None = None) -> None:
        self.level = level or level_io.new_level("level_editor", width_tiles=60, height_tiles=11)
        self.level.setdefault("saws", [])
        self.assets = get_asset_manager()
        self.mode = "tiles"
        self.cam_x = 0.0
        self.cam_y = 0.0
        self.zoom = 1.0
        self.brush = 1
        self.show_grid = True
        self.show_hitboxes = False
        self.eraser = False
        self.message = "Редактор: ЛКМ — поставить, ПКМ/Ластик — удалить, T — тест, Ctrl+S — save"
        # выбранные индексы ассетов по категориям
        self.sel = {"tiles": 0, "items": 0, "enemies": 0, "obstacles": 0, "background": 0}
        # размер окна (можно растягивать) и рабочая область
        self.width = EDITOR_W
        self.height = EDITOR_H
        self.canvas = pygame.Rect(PALETTE_W, TOOLBAR_H, EDITOR_W - PALETTE_W, EDITOR_H - TOOLBAR_H)
        # история изменений (undo/redo)
        self._undo: list[dict] = []
        self._redo: list[dict] = []
        # черновик пилы и её параметры
        self.saw_draft: tuple[float, float] | None = None
        self.saw_r = 26.0
        self.saw_period = 2.4
        self.saw_phase = 0.0  # 0 = вперёд (к концу), pi = назад (к старту)
        # UI: физически зажатые клавиши (камера), мышиные элементы
        self.held_sc: set[int] = set()
        self.dropdown_open = False
        self.load_open = False
        self.ui: dict[str, pygame.Rect] = {}
        self.palette_rects: list[tuple[pygame.Rect, int]] = []
        self.dropdown_rects: list[tuple[pygame.Rect, str]] = []
        self.load_rects: list[tuple[pygame.Rect, Path]] = []

    def _held(self, *scancodes: int) -> bool:
        return any(s in self.held_sc for s in scancodes)

    # ---------- размер окна ----------
    def set_size(self, w: int, h: int) -> None:
        self.width = max(720, w)
        self.height = max(420, h)
        self.canvas = pygame.Rect(PALETTE_W, TOOLBAR_H,
                                  self.width - PALETTE_W, self.height - TOOLBAR_H)

    # ---------- история (undo/redo) ----------
    def push_undo(self) -> None:
        self._undo.append(copy.deepcopy(self.level))
        if len(self._undo) > 60:
            self._undo.pop(0)
        self._redo.clear()

    def undo(self) -> None:
        if not self._undo:
            self.message = "Откатывать нечего"
            return
        self._redo.append(copy.deepcopy(self.level))
        self.level = self._undo.pop()
        self.saw_draft = None
        self.message = "Отменено (Ctrl+Z)"

    def redo(self) -> None:
        if not self._redo:
            self.message = "Повторять нечего"
            return
        self._undo.append(copy.deepcopy(self.level))
        self.level = self._redo.pop()
        self.message = "Повторено (Ctrl+Y)"

    def is_saw_tool(self) -> bool:
        return self.mode == "obstacles" and self.selected_id("obstacles") == "saw"

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.message = f"Режим: {MODE_LABELS.get(mode, mode)}"

    def on_mouse_down(self, pos: tuple[int, int], button: int) -> str | None:
        """Обработка клика мыши по UI/холсту. Возвращает 'test' для playtest."""
        if button == 3:
            if self.canvas.collidepoint(pos):
                self.push_undo()
                self.erase(*pos)
            return None
        if button != 1:
            return None
        # открытый список файлов для загрузки
        if self.load_open:
            for rect, path in self.load_rects:
                if rect.collidepoint(pos):
                    self.load_open = False
                    self.load_path(path)
                    return None
            self.load_open = False
            return None
        # открытый выпадающий список режимов
        if self.dropdown_open:
            for rect, mode in self.dropdown_rects:
                if rect.collidepoint(pos):
                    self.dropdown_open = False
                    if mode == "test":
                        return "test"
                    self.set_mode(mode)
                    return None
            self.dropdown_open = False
            return None
        # кнопки верхней панели
        for name, rect in self.ui.items():
            if rect.collidepoint(pos):
                if name == "save":
                    self.save()
                elif name == "load":
                    self.load_open = not self.load_open
                elif name == "test":
                    return "test"
                elif name == "mode":
                    self.dropdown_open = True
                elif name == "eraser":
                    self.eraser = not self.eraser
                    self.message = "Ластик ВКЛ (ЛКМ стирает)" if self.eraser else "Ластик ВЫКЛ"
                elif name == "undo":
                    self.undo()
                elif name == "redo":
                    self.redo()
                elif name == "grow_up":
                    self.grow_up(2)
                elif name == "grow_down":
                    self.grow_down(2)
                elif name == "saw_r_dec":
                    self.saw_r = max(10.0, self.saw_r - 2)
                elif name == "saw_r_inc":
                    self.saw_r = min(60.0, self.saw_r + 2)
                elif name == "saw_t_dec":
                    self.saw_period = max(0.6, round(self.saw_period - 0.2, 2))
                elif name == "saw_t_inc":
                    self.saw_period = min(8.0, round(self.saw_period + 0.2, 2))
                elif name == "saw_dir":
                    self.saw_phase = 0.0 if self.saw_phase else math.pi
                return None
        # клик по строке палитры → выбрать ассет
        for rect, idx in self.palette_rects:
            if rect.collidepoint(pos):
                cat = self.mode if self.mode in self.sel else None
                if cat is not None:
                    self.sel[cat] = idx
                    self.message = f"{self.mode}: {self.selected_id(cat)}"
                    self.saw_draft = None
                return None
        # клик по холсту
        if self.canvas.collidepoint(pos):
            if self.eraser:
                self.push_undo()
                self.erase(*pos)
            elif self.is_saw_tool():
                if self.saw_draft is not None:
                    self.push_undo()  # фиксируем добавление пилы
                self.place(*pos)
            else:
                self.push_undo()
                self.place(*pos)
        return None

    # ---------- геометрия ----------
    @property
    def tile_size(self) -> int:
        return int(self.level["tile_size"])

    def world_to_screen(self, wx: float, wy: float) -> tuple[int, int]:
        return (
            int((wx - self.cam_x) * self.zoom + self.canvas.x),
            int((wy - self.cam_y) * self.zoom + self.canvas.y),
        )

    def screen_to_world(self, sx: float, sy: float) -> tuple[float, float]:
        return (
            (sx - self.canvas.x) / self.zoom + self.cam_x,
            (sy - self.canvas.y) / self.zoom + self.cam_y,
        )

    def cell_at(self, sx: float, sy: float) -> tuple[int, int]:
        wx, wy = self.screen_to_world(sx, sy)
        ts = self.tile_size
        return int(wx // ts), int(wy // ts)

    # ---------- палитра/категории ----------
    def _cat_ids(self) -> list[str]:
        return {
            "tiles": TILE_IDS,
            "items": ITEM_IDS,
            "enemies": ENEMY_IDS,
            "obstacles": OBSTACLE_IDS,
            "background": BACKGROUND_IDS,
        }.get(self.mode, [])

    def cycle_asset(self, delta: int) -> None:
        ids = self._cat_ids()
        if not ids or self.mode not in self.sel:
            return
        self.sel[self.mode] = (self.sel[self.mode] + delta) % len(ids)
        self.message = f"{self.mode}: {ids[self.sel[self.mode]]}"

    def selected_id(self, category: str) -> str:
        ids = {
            "tiles": TILE_IDS, "items": ITEM_IDS, "enemies": ENEMY_IDS,
            "obstacles": OBSTACLE_IDS, "background": BACKGROUND_IDS,
        }[category]
        return ids[self.sel[category] % len(ids)]

    # ---------- размещение/удаление (вызываемо и без UI) ----------
    def place(self, sx: float, sy: float) -> None:
        ts = self.tile_size
        cx, cy = self.cell_at(sx, sy)
        wx, wy = self.screen_to_world(sx, sy)
        if self.mode == "tiles":
            for dx in range(self.brush):
                for dy in range(self.brush):
                    self._set_tile(cx + dx, cy + dy, self.selected_id("tiles"))
        elif self.mode == "platforms":
            self.level["platforms"].append({
                "x": cx * ts, "y": cy * ts,
                "width": self.brush * ts, "height": ts // 2,
                "tile_id": self.selected_id("tiles"),
            })
        elif self.mode == "enemies":
            self.level["enemies"].append({
                "x": cx * ts, "y": cy * ts,
                "enemy_type": self.selected_id("enemies"),
                "asset_id": self.selected_id("enemies"),
                "properties": {"patrol_left": cx * ts - 80, "patrol_right": cx * ts + 80},
            })
        elif self.mode == "items":
            self.level["items"].append({
                "x": cx * ts + ts // 2, "y": cy * ts + ts // 2,
                "item_type": self.selected_id("items"),
                "asset_id": self.selected_id("items"),
            })
        elif self.mode == "obstacles":
            if self.selected_id("obstacles") == "saw":
                self._place_saw(wx, wy)
            else:
                self.level["obstacles"].append({
                    "x": cx * ts, "y": cy * ts + ts - 18,
                    "width": ts, "height": 18,
                    "obstacle_type": self.selected_id("obstacles"),
                    "asset_id": self.selected_id("obstacles"),
                })
        elif self.mode == "player_start":
            self.level["player"]["start_x"] = int(wx)
            self.level["player"]["start_y"] = int(wy)
            self.message = "Старт игрока установлен"
        elif self.mode == "level_end":
            self.level["level_end"]["x"] = int(wx)
            self.level["level_end"]["y"] = int(wy)
            self.message = "Конец уровня установлен"
        elif self.mode == "background":
            self.level["background"] = self.selected_id("background")
            self.message = f"Фон: {self.level['background']}"

    def erase(self, sx: float, sy: float) -> None:
        ts = self.tile_size
        cx, cy = self.cell_at(sx, sy)
        wx, wy = self.screen_to_world(sx, sy)
        self._del_tile(cx, cy)
        for key in ("platforms", "enemies", "items", "obstacles"):
            self._del_object_at(key, wx, wy)
        self._del_saw_at(wx, wy)

    # ---------- пилы ----------
    def _place_saw(self, wx: float, wy: float) -> None:
        if self.saw_draft is None:
            self.saw_draft = (wx, wy)
            self.message = "Пила: кликни КОНЕЦ маршрута (точка = на месте)"
            return
        x1, y1 = self.saw_draft
        self.level.setdefault("saws", []).append({
            "x1": round(x1), "y1": round(y1),
            "x2": round(wx), "y2": round(wy),
            "r": round(self.saw_r), "period": round(self.saw_period, 2),
            "phase": round(self.saw_phase, 3),
        })
        self.saw_draft = None
        self.message = "Пила добавлена (маршрут, размер, скорость, направление)"

    def _del_saw_at(self, wx: float, wy: float) -> None:
        saws = self.level.get("saws", [])
        keep = []
        for sw in saws:
            # рядом с любым концом маршрута или его серединой → удалить
            pts = [(sw["x1"], sw["y1"]), (sw["x2"], sw["y2"]),
                   ((sw["x1"] + sw["x2"]) / 2, (sw["y1"] + sw["y2"]) / 2)]
            hit = any((wx - px) ** 2 + (wy - py) ** 2 <= (sw.get("r", 26) + 6) ** 2
                      for px, py in pts)
            if not hit:
                keep.append(sw)
        self.level["saws"] = keep

    def _set_tile(self, cx: int, cy: int, tile_id: str) -> None:
        if not (0 <= cx < self.level["width_tiles"] and 0 <= cy < self.level["height_tiles"]):
            return
        for t in self.level["tiles"]:
            if t["x"] == cx and t["y"] == cy:
                t["tile_id"] = tile_id
                return
        self.level["tiles"].append({"x": cx, "y": cy, "tile_id": tile_id})

    def _del_tile(self, cx: int, cy: int) -> None:
        self.level["tiles"] = [
            t for t in self.level["tiles"] if not (t["x"] == cx and t["y"] == cy)
        ]

    def _del_object_at(self, key: str, wx: float, wy: float) -> None:
        ts = self.tile_size
        keep = []
        for o in self.level[key]:
            ox, oy = o["x"], o["y"]
            w = o.get("width", ts)
            h = o.get("height", ts)
            if ox <= wx <= ox + w and oy <= wy <= oy + h:
                continue  # удаляем
            keep.append(o)
        self.level[key] = keep

    # ---------- размер уровня ----------
    def resize_width(self, delta_tiles: int) -> None:
        self.push_undo()
        new_w = max(10, self.level["width_tiles"] + delta_tiles)
        if delta_tiles < 0:
            lost = self._objects_beyond(new_w * self.tile_size, None)
            if lost:
                self.message = f"ВНИМАНИЕ: за границей окажется объектов: {lost}"
        self.level["width_tiles"] = new_w
        self.message = f"Ширина уровня: {new_w} тайлов"

    def resize_height(self, delta_tiles: int) -> None:
        self.push_undo()
        new_h = max(7, self.level["height_tiles"] + delta_tiles)
        if delta_tiles < 0:
            lost = self._objects_beyond(None, new_h * self.tile_size)
            if lost:
                self.message = f"ВНИМАНИЕ: за границей окажется объектов: {lost}"
        self.level["height_tiles"] = new_h
        self.message = f"Высота уровня: {new_h} тайлов"

    def _objects_beyond(self, max_x: float | None, max_y: float | None) -> int:
        n = 0
        ts = self.tile_size
        for t in self.level["tiles"]:
            if max_x is not None and t["x"] * ts >= max_x:
                n += 1
            if max_y is not None and t["y"] * ts >= max_y:
                n += 1
        for key in ("platforms", "enemies", "items", "obstacles"):
            for o in self.level[key]:
                if max_x is not None and o["x"] >= max_x:
                    n += 1
                if max_y is not None and o["y"] >= max_y:
                    n += 1
        return n

    def grow_up(self, delta_tiles: int = 2) -> None:
        """Нарастить уровень сверху: добавить ряды над сценой, сдвинув всё вниз."""
        self.push_undo()
        ts = self.tile_size
        dy_px = delta_tiles * ts
        self.level["height_tiles"] += delta_tiles
        for t in self.level["tiles"]:
            t["y"] += delta_tiles
        for key in ("platforms", "enemies", "items", "obstacles"):
            for o in self.level[key]:
                o["y"] += dy_px
        for sw in self.level.get("saws", []):
            sw["y1"] += dy_px
            sw["y2"] += dy_px
        self.level["player"]["start_y"] += dy_px
        self.level["level_end"]["y"] += dy_px
        self.cam_y += dy_px
        self.message = f"Сверху добавлено {delta_tiles} рядов (высота {self.level['height_tiles']})"

    def grow_down(self, delta_tiles: int = 2) -> None:
        """Нарастить уровень снизу: добавить ряды под сценой (объекты на месте)."""
        self.push_undo()
        self.level["height_tiles"] += delta_tiles
        self.message = f"Снизу добавлено {delta_tiles} рядов (высота {self.level['height_tiles']})"

    # ---------- save / load ----------
    def _load_files(self) -> list[Path]:
        if not level_io.LEVELS_DIR.is_dir():
            return []
        files = sorted(
            p for p in level_io.LEVELS_DIR.glob("*.json")
            if not p.name.startswith("_")
        )
        return files

    def load_path(self, path: Path) -> None:
        try:
            self.level = level_io.load_level_file(path)
            self.level.setdefault("saws", [])
            self.level["name"] = path.stem  # чтобы Save писал в тот же файл
            self._undo.clear()
            self._redo.clear()
            self.saw_draft = None
            self.cam_x = self.cam_y = 0.0
            self.message = f"Загружено: {path.name}"
        except ValueError as e:
            self.message = f"Не удалось загрузить: {e}"
            print(f"[editor] load error: {e}")

    def save(self) -> Path:
        path = level_io.LEVELS_DIR / f"{self.level.get('name', 'level_editor')}.json"
        level_io.save_level(self.level, path)
        self.message = f"Сохранено: {path.name}"
        print(f"[editor] saved → {path}")
        return path

    def load(self) -> None:
        path = level_io.LEVELS_DIR / f"{self.level.get('name', 'level_editor')}.json"
        try:
            self.level = level_io.load_level_file(path)
            self.message = f"Загружено: {path.name}"
        except ValueError as e:
            self.message = f"Не удалось загрузить: {e}"
            print(f"[editor] load error: {e}")

    def save_test_level(self) -> Path:
        path = level_io.LEVELS_DIR / "_editor_test_level.json"
        return level_io.save_level(self.level, path)


# ---------- отрисовка и главный цикл ----------

def run_editor(level_path: str | None = None) -> None:
    if not pygame.get_init():
        pygame.init()
    screen = pygame.display.set_mode((EDITOR_W, EDITOR_H), pygame.RESIZABLE)
    pygame.display.set_caption("Level Editor")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("arial", 16)
    font_small = pygame.font.SysFont("arial", 13)

    start_level = None
    if level_path and Path(level_path).is_file():
        try:
            start_level = level_io.load_level_file(level_path)
        except ValueError as e:
            print(f"[editor] {e}")
    ed = LevelEditor(start_level)

    am = ed.assets

    def tile_surface(tile_id: str, size: int) -> pygame.Surface:
        return am.scaled(am.tile(tile_id), (size, size))

    def do_test() -> None:
        nonlocal screen
        _playtest(ed)
        screen = pygame.display.set_mode((ed.width, ed.height), pygame.RESIZABLE)
        pygame.display.set_caption("Level Editor")

    def sc(event) -> int:
        return getattr(event, "scancode", -1)

    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        mods = pygame.key.get_mods()
        ctrl = mods & pygame.KMOD_CTRL

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                ed.set_size(event.w, event.h)
                screen = pygame.display.set_mode((ed.width, ed.height), pygame.RESIZABLE)
            elif event.type == pygame.KEYUP:
                ed.held_sc.discard(sc(event))
            elif event.type == pygame.KEYDOWN:
                s = sc(event)
                ed.held_sc.add(s)
                if s == pygame.KSCAN_ESCAPE or event.key == pygame.K_ESCAPE:
                    if ed.dropdown_open or ed.load_open:
                        ed.dropdown_open = ed.load_open = False
                    elif ed.saw_draft is not None:
                        ed.saw_draft = None
                        ed.message = "Черновик пилы отменён"
                    else:
                        running = False
                elif s == pygame.KSCAN_Z and ctrl:
                    ed.undo()
                elif s in (pygame.KSCAN_Y,) and ctrl:
                    ed.redo()
                elif s in MODES_SC:
                    m = MODES_SC[s]
                    if m == "test":
                        do_test()
                    else:
                        ed.set_mode(m)
                elif s == pygame.KSCAN_S and ctrl:
                    ed.save()
                elif s == pygame.KSCAN_O and ctrl:
                    ed.load()
                elif s == pygame.KSCAN_T:
                    do_test()
                elif s == pygame.KSCAN_G:
                    ed.show_grid = not ed.show_grid
                elif s == pygame.KSCAN_H:
                    ed.show_hitboxes = not ed.show_hitboxes
                elif s in (pygame.KSCAN_EQUALS, pygame.KSCAN_KP_PLUS):
                    ed.zoom = min(2.0, ed.zoom + 0.1)
                elif s in (pygame.KSCAN_MINUS, pygame.KSCAN_KP_MINUS):
                    ed.zoom = max(0.4, ed.zoom - 0.1)
                elif s == pygame.KSCAN_LEFTBRACKET:
                    ed.brush = max(1, ed.brush - 1)
                elif s == pygame.KSCAN_RIGHTBRACKET:
                    ed.brush = min(8, ed.brush + 1)
                elif s == pygame.KSCAN_PERIOD:
                    ed.resize_width(5)
                elif s == pygame.KSCAN_COMMA:
                    ed.resize_width(-5)
                elif s == pygame.KSCAN_PAGEUP:
                    ed.resize_height(2)
                elif s == pygame.KSCAN_PAGEDOWN:
                    ed.resize_height(-2)
            elif event.type == pygame.MOUSEWHEEL:
                ed.cycle_asset(1 if event.y > 0 else -1)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if ed.on_mouse_down(event.pos, event.button) == "test":
                    do_test()

        # перетаскивание мыши: рисование тайлов / стирание ластиком (вне UI)
        buttons = pygame.mouse.get_pressed(3)
        mx, my = pygame.mouse.get_pos()
        menus_open = ed.dropdown_open or ed.load_open
        if not menus_open and ed.canvas.collidepoint(mx, my):
            if buttons[0] and ed.eraser:
                ed.erase(mx, my)
            elif buttons[0] and ed.mode == "tiles":
                ed.place(mx, my)
            elif buttons[2]:
                ed.erase(mx, my)

        # камера: WASD/стрелки (scancode — любая раскладка)
        pan = 360 * dt / ed.zoom
        if ed._held(*SC_CAM_LEFT):
            ed.cam_x -= pan
        if ed._held(*SC_CAM_RIGHT):
            ed.cam_x += pan
        if ed._held(*SC_CAM_UP):
            ed.cam_y -= pan
        if ed._held(*SC_CAM_DOWN):
            ed.cam_y += pan
        ed.cam_x = max(-200, min(ed.cam_x, ed.level["width_tiles"] * ed.tile_size))
        ed.cam_y = max(-200, min(ed.cam_y, ed.level["height_tiles"] * ed.tile_size))

        _draw_editor(screen, ed, font, font_small, tile_surface)
        pygame.display.flip()

    # выходим из редактора, окно остаётся за вызывающим


def _playtest(ed: LevelEditor) -> None:
    import platformer as P

    ed.save_test_level()
    try:
        ld = level_io.dict_to_leveldata(ed.level)
    except ValueError as e:
        ed.message = f"Тест невозможен: {e}"
        return
    game = P.PlatformerGame()
    game.play_level_data(ld)
    game.run(quit_pygame_on_exit=False)  # Esc (дважды) возвращает в редактор


def _draw_editor(screen, ed: LevelEditor, font, font_small, tile_surface) -> None:
    screen.fill(BG)
    ed.ui = {}
    ts = ed.tile_size
    am = ed.assets

    # --- рабочая область ---
    prev_clip = screen.get_clip()
    screen.set_clip(ed.canvas)

    # фоновая рамка уровня
    lw = ed.level["width_tiles"] * ts
    lh = ed.level["height_tiles"] * ts
    ox, oy = ed.world_to_screen(0, 0)
    pygame.draw.rect(screen, (22, 26, 36),
                     (ox, oy, int(lw * ed.zoom), int(lh * ed.zoom)))

    # сетка
    if ed.show_grid:
        step = ts * ed.zoom
        x = ox
        col = 0
        while x < ed.canvas.right and col <= ed.level["width_tiles"]:
            if x >= ed.canvas.left:
                pygame.draw.line(screen, GRID, (x, max(oy, ed.canvas.top)),
                                 (x, min(oy + lh * ed.zoom, ed.canvas.bottom)))
            x += step
            col += 1
        y = oy
        row = 0
        while y < ed.canvas.bottom and row <= ed.level["height_tiles"]:
            if y >= ed.canvas.top:
                pygame.draw.line(screen, GRID, (max(ox, ed.canvas.left), y),
                                 (min(ox + lw * ed.zoom, ed.canvas.right), y))
            y += step
            row += 1

    size = max(4, int(ts * ed.zoom))

    # тайлы
    for t in ed.level["tiles"]:
        sx, sy = ed.world_to_screen(t["x"] * ts, t["y"] * ts)
        screen.blit(tile_surface(t["tile_id"], size), (sx, sy))

    # платформы
    for pl in ed.level["platforms"]:
        sx, sy = ed.world_to_screen(pl["x"], pl["y"])
        w = int(pl["width"] * ed.zoom)
        h = int(pl["height"] * ed.zoom)
        tile = am.scaled(am.tile(pl.get("tile_id", "grass")), (max(4, size), max(4, int(h))))
        cx = sx
        while cx < sx + w:
            screen.blit(tile, (cx, sy))
            cx += size
        if ed.show_hitboxes:
            pygame.draw.rect(screen, (255, 0, 0), (sx, sy, w, h), 1)

    # препятствия
    for ob in ed.level["obstacles"]:
        sx, sy = ed.world_to_screen(ob["x"], ob["y"])
        w = int(ob.get("width", ts) * ed.zoom)
        h = int(ob.get("height", ts) * ed.zoom)
        screen.blit(am.scaled(am.obstacle(ob.get("asset_id", "spikes")), (max(4, w), max(4, h))), (sx, sy))

    # предметы
    for it in ed.level["items"]:
        sx, sy = ed.world_to_screen(it["x"], it["y"])
        spr = am.scaled(am.item(it.get("asset_id", "coin")), (size, size))
        screen.blit(spr, (sx - size // 2, sy - size // 2))

    # враги
    for en in ed.level["enemies"]:
        sx, sy = ed.world_to_screen(en["x"], en["y"])
        frames = am.enemy_frames(en.get("asset_id", "slime"))
        screen.blit(am.scaled(frames[0], (size, size)), (sx, sy))

    # пилы: маршрут + пила в начальной точке
    saw_spr = am.obstacle("saw")
    for sw in ed.level.get("saws", []):
        ax, ay = ed.world_to_screen(sw["x1"], sw["y1"])
        bx, by = ed.world_to_screen(sw["x2"], sw["y2"])
        pygame.draw.line(screen, (255, 120, 120), (ax, ay), (bx, by), 2)
        pygame.draw.circle(screen, (120, 200, 255), (bx, by), 4)  # конец
        d = int(sw.get("r", 26) * 2 * ed.zoom)
        spr = am.scaled(saw_spr, (max(6, d), max(6, d)))
        # начало маршрута зависит от направления (phase)
        start = (bx, by) if sw.get("phase", 0) else (ax, ay)
        screen.blit(spr, (start[0] - d // 2, start[1] - d // 2))
        if ed.show_hitboxes:
            pygame.draw.circle(screen, (255, 0, 0), start, int(sw.get("r", 26) * ed.zoom), 1)

    # черновик пилы (ждём вторую точку)
    if ed.saw_draft is not None:
        dx, dy = ed.world_to_screen(*ed.saw_draft)
        mxp, myp = pygame.mouse.get_pos()
        pygame.draw.line(screen, (255, 180, 90), (dx, dy), (mxp, myp), 1)
        d = int(ed.saw_r * 2 * ed.zoom)
        spr = am.scaled(saw_spr, (max(6, d), max(6, d)))
        screen.blit(spr, (dx - d // 2, dy - d // 2))

    # старт игрока и конец уровня
    psx, psy = ed.world_to_screen(ed.level["player"]["start_x"], ed.level["player"]["start_y"])
    pygame.draw.rect(screen, (90, 200, 255), (psx - 6, psy - 14, 14, 18), 2)
    screen.blit(font_small.render("START", True, (90, 200, 255)), (psx - 12, psy - 30))
    lex, ley = ed.world_to_screen(ed.level["level_end"]["x"], ed.level["level_end"]["y"])
    screen.blit(am.scaled(am.item("flag"), (size, int(size * 1.6))), (lex, ley - size))
    screen.blit(font_small.render("END", True, (120, 255, 150)), (lex, ley - size - 16))

    # курсор-подсветка (красный для ластика)
    mx, my = pygame.mouse.get_pos()
    if ed.canvas.collidepoint(mx, my):
        cx, cy = ed.cell_at(mx, my)
        hsx, hsy = ed.world_to_screen(cx * ts, cy * ts)
        cur_col = (255, 90, 90) if ed.eraser else ACCENT
        pygame.draw.rect(screen, cur_col, (hsx, hsy, size, size), 2)

    screen.set_clip(prev_clip)

    # --- палитра слева ---
    pygame.draw.rect(screen, PANEL, (0, TOOLBAR_H, PALETTE_W, ed.height - TOOLBAR_H))
    y = TOOLBAR_H + 10
    cat = ed.mode if ed.mode in ed.sel else None
    title = f"Палитра: {ed.mode}"
    screen.blit(font.render(title, True, TEXT), (10, y))
    y += 26
    ids = ed._cat_ids()
    ed.palette_rects = []
    for i, aid in enumerate(ids):
        rect = pygame.Rect(10, y, PALETTE_W - 20, 36)
        ed.palette_rects.append((rect, i))
        sel = cat and i == ed.sel.get(cat, 0)
        pygame.draw.rect(screen, PANEL_HI if sel else (52, 58, 76), rect, border_radius=4)
        # превью
        try:
            if ed.mode == "tiles":
                prev = am.scaled(am.tile(aid), (28, 28))
            elif ed.mode == "items":
                prev = am.scaled(am.item(aid), (28, 28))
            elif ed.mode == "enemies":
                prev = am.scaled(am.enemy_frames(aid)[0], (28, 28))
            elif ed.mode == "obstacles":
                prev = am.scaled(am.obstacle(aid), (28, 28))
            elif ed.mode == "background":
                prev = am.scaled(am.background(aid), (28, 28))
            else:
                prev = None
            if prev is not None:
                screen.blit(prev, (rect.x + 4, rect.y + 4))
        except Exception:  # noqa: BLE001
            pass
        screen.blit(font_small.render(aid, True, TEXT), (rect.x + 38, rect.y + 10))
        y += 42
        if y > ed.height - 200:
            break

    # --- настройки пилы (когда выбран инструмент «saw») ---
    if ed.is_saw_tool():
        _draw_saw_settings(screen, ed, font, font_small, y + 6)

    # подсказка режимов
    hy = ed.height - 78
    for line in [
        "ЛКМ/Ластик — ставить/стирать",
        "[ ] кисть  + - зум  G сетка  H хитб.",
        "Ctrl+Z/Y — отмена/повтор  T тест",
    ]:
        screen.blit(font_small.render(line, True, TEXT_DIM), (10, hy))
        hy += 18

    # --- верхняя панель с кликабельными кнопками ---
    pygame.draw.rect(screen, (24, 28, 38), (0, 0, ed.width, TOOLBAR_H))

    def button(name, label, x, w, active=False):
        rect = pygame.Rect(x, 6, w, 26)
        hover = rect.collidepoint(pygame.mouse.get_pos())
        bg = ACCENT if active else (PANEL_HI if hover else PANEL)
        pygame.draw.rect(screen, bg, rect, border_radius=6)
        pygame.draw.rect(screen, (90, 100, 130), rect, 1, border_radius=6)
        fg = (20, 24, 32) if active else TEXT
        lab = font_small.render(label, True, fg)
        screen.blit(lab, (rect.centerx - lab.get_width() // 2, rect.centery - lab.get_height() // 2))
        ed.ui[name] = rect
        return rect.right

    x = 10
    x = button("save", "Save", x, 52) + 5
    x = button("load", "Load v", x, 58, active=ed.load_open) + 5
    x = button("test", "Test", x, 50) + 12
    mode_rect = pygame.Rect(x, 6, 150, 26)
    hover = mode_rect.collidepoint(pygame.mouse.get_pos())
    pygame.draw.rect(screen, PANEL_HI if (hover or ed.dropdown_open) else PANEL, mode_rect, border_radius=6)
    pygame.draw.rect(screen, (90, 100, 130), mode_rect, 1, border_radius=6)
    mlab = font_small.render(f"Режим: {MODE_LABELS.get(ed.mode, ed.mode)} v", True, TEXT)
    screen.blit(mlab, (mode_rect.x + 8, mode_rect.centery - mlab.get_height() // 2))
    ed.ui["mode"] = mode_rect
    x = mode_rect.right + 12
    x = button("eraser", "Ластик", x, 64, active=ed.eraser) + 5
    x = button("undo", "Undo", x, 50) + 5
    x = button("redo", "Redo", x, 50) + 12
    x = button("grow_up", "Выше +", x, 64) + 5
    x = button("grow_down", "Ниже +", x, 64) + 5

    info = (
        f"кисть:{ed.brush}  зум:{ed.zoom:.1f}  "
        f"размер:{ed.level['width_tiles']}x{ed.level['height_tiles']}  "
        f"имя:{ed.level.get('name','')}"
    )
    screen.blit(font_small.render(info, True, TEXT_DIM), (10, 38))
    msg = font_small.render(ed.message, True, ACCENT)
    screen.blit(msg, (ed.width - msg.get_width() - 10, 38))

    # выпадающий список режимов (рисуем поверх всего)
    ed.dropdown_rects = []
    if ed.dropdown_open:
        dx, dy = mode_rect.x, mode_rect.bottom + 2
        dw, dh = mode_rect.width, 24
        for m in MODE_ORDER:
            r = pygame.Rect(dx, dy, dw, dh)
            ed.dropdown_rects.append((r, m))
            hov = r.collidepoint(pygame.mouse.get_pos())
            pygame.draw.rect(screen, PANEL_HI if hov else PANEL, r)
            pygame.draw.rect(screen, (90, 100, 130), r, 1)
            active = m == ed.mode
            col = ACCENT if active else TEXT
            screen.blit(font_small.render(MODE_LABELS.get(m, m), True, col), (r.x + 8, r.y + 5))
            dy += dh

    # выпадающий список файлов для загрузки
    ed.load_rects = []
    if ed.load_open:
        files = ed._load_files()
        lr = ed.ui["load"]
        dx, dy, dw, dh = lr.x, lr.bottom + 2, 220, 24
        if not files:
            r = pygame.Rect(dx, dy, dw, dh)
            pygame.draw.rect(screen, PANEL, r)
            pygame.draw.rect(screen, (90, 100, 130), r, 1)
            screen.blit(font_small.render("нет файлов в levels/", True, TEXT_DIM), (r.x + 8, r.y + 5))
        for p in files:
            r = pygame.Rect(dx, dy, dw, dh)
            ed.load_rects.append((r, p))
            hov = r.collidepoint(pygame.mouse.get_pos())
            pygame.draw.rect(screen, PANEL_HI if hov else PANEL, r)
            pygame.draw.rect(screen, (90, 100, 130), r, 1)
            screen.blit(font_small.render(p.name, True, TEXT), (r.x + 8, r.y + 5))
            dy += dh


def _draw_saw_settings(screen, ed: LevelEditor, font, font_small, y: int) -> None:
    """Панель параметров пилы: размер, период (скорость), направление."""
    box = pygame.Rect(6, y, PALETTE_W - 12, 132)
    pygame.draw.rect(screen, (34, 40, 56), box, border_radius=6)
    pygame.draw.rect(screen, (90, 100, 130), box, 1, border_radius=6)
    screen.blit(font.render("Пила", True, ACCENT), (box.x + 8, box.y + 6))
    mp = pygame.mouse.get_pos()

    def step_row(name_dec, name_inc, label, value, ry):
        screen.blit(font_small.render(label, True, TEXT), (box.x + 8, ry))
        dec = pygame.Rect(box.right - 86, ry - 2, 22, 20)
        inc = pygame.Rect(box.right - 30, ry - 2, 22, 20)
        for r, txt, nm in ((dec, "-", name_dec), (inc, "+", name_inc)):
            hov = r.collidepoint(mp)
            pygame.draw.rect(screen, PANEL_HI if hov else PANEL, r, border_radius=4)
            pygame.draw.rect(screen, (90, 100, 130), r, 1, border_radius=4)
            t = font_small.render(txt, True, TEXT)
            screen.blit(t, (r.centerx - t.get_width() // 2, r.centery - t.get_height() // 2))
            ed.ui[nm] = r
        val = font_small.render(value, True, ACCENT)
        screen.blit(val, (box.right - 64, ry))

    step_row("saw_r_dec", "saw_r_inc", "Размер", f"{int(ed.saw_r)}", box.y + 32)
    step_row("saw_t_dec", "saw_t_inc", "Период", f"{ed.saw_period:.1f}с", box.y + 58)

    # направление
    screen.blit(font_small.render("Направл.", True, TEXT), (box.x + 8, box.y + 84))
    dr = pygame.Rect(box.right - 86, box.y + 82, 78, 20)
    hov = dr.collidepoint(mp)
    pygame.draw.rect(screen, PANEL_HI if hov else PANEL, dr, border_radius=4)
    pygame.draw.rect(screen, (90, 100, 130), dr, 1, border_radius=4)
    dir_txt = "назад" if ed.saw_phase else "вперёд"
    t = font_small.render(dir_txt, True, TEXT)
    screen.blit(t, (dr.centerx - t.get_width() // 2, dr.centery - t.get_height() // 2))
    ed.ui["saw_dir"] = dr

    hint = "ЛКМ: старт → конец" if ed.saw_draft is None else "ЛКМ: задай конец"
    screen.blit(font_small.render(hint, True, TEXT_DIM), (box.x + 8, box.y + 108))


if __name__ == "__main__":
    run_editor()
