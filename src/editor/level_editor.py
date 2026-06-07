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
TOOLBAR_H = 40

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


class LevelEditor:
    def __init__(self, level: dict | None = None) -> None:
        self.level = level or level_io.new_level("level_editor", width_tiles=60, height_tiles=11)
        self.assets = get_asset_manager()
        self.mode = "tiles"
        self.cam_x = 0.0
        self.cam_y = 0.0
        self.zoom = 1.0
        self.brush = 1
        self.show_grid = True
        self.show_hitboxes = False
        self.message = "Редактор: ЛКМ — поставить, ПКМ — удалить, T — тест, Ctrl+S — save"
        # выбранные индексы ассетов по категориям
        self.sel = {"tiles": 0, "items": 0, "enemies": 0, "obstacles": 0, "background": 0}
        self.canvas = pygame.Rect(PALETTE_W, TOOLBAR_H, EDITOR_W - PALETTE_W, EDITOR_H - TOOLBAR_H)

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
        new_w = max(10, self.level["width_tiles"] + delta_tiles)
        if delta_tiles < 0:
            lost = self._objects_beyond(new_w * self.tile_size, None)
            if lost:
                self.message = f"ВНИМАНИЕ: за границей окажется объектов: {lost}"
        self.level["width_tiles"] = new_w
        self.message = f"Ширина уровня: {new_w} тайлов"

    def resize_height(self, delta_tiles: int) -> None:
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

    # ---------- save / load ----------
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
    screen = pygame.display.set_mode((EDITOR_W, EDITOR_H))
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

    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        mods = pygame.key.get_mods()
        ctrl = mods & pygame.KMOD_CTRL

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key in MODES:
                    m = MODES[event.key]
                    if m == "test":
                        _playtest(ed)
                        screen = pygame.display.set_mode((EDITOR_W, EDITOR_H))
                        pygame.display.set_caption("Level Editor")
                    else:
                        ed.mode = m
                        ed.message = f"Режим: {MODE_LABELS[m]}"
                elif event.key == pygame.K_s and ctrl:
                    ed.save()
                elif event.key == pygame.K_o and ctrl:
                    ed.load()
                elif event.key == pygame.K_t:
                    _playtest(ed)
                    screen = pygame.display.set_mode((EDITOR_W, EDITOR_H))
                    pygame.display.set_caption("Level Editor")
                elif event.key == pygame.K_g:
                    ed.show_grid = not ed.show_grid
                elif event.key == pygame.K_h:
                    ed.show_hitboxes = not ed.show_hitboxes
                elif event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                    ed.zoom = min(2.0, ed.zoom + 0.1)
                elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    ed.zoom = max(0.4, ed.zoom - 0.1)
                elif event.key == pygame.K_LEFTBRACKET:
                    ed.brush = max(1, ed.brush - 1)
                elif event.key == pygame.K_RIGHTBRACKET:
                    ed.brush = min(8, ed.brush + 1)
                elif event.key == pygame.K_PERIOD:
                    ed.resize_width(5)
                elif event.key == pygame.K_COMMA:
                    ed.resize_width(-5)
                elif event.key == pygame.K_PAGEUP:
                    ed.resize_height(2)
                elif event.key == pygame.K_PAGEDOWN:
                    ed.resize_height(-2)
            elif event.type == pygame.MOUSEWHEEL:
                ed.cycle_asset(1 if event.y > 0 else -1)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                if ed.canvas.collidepoint(mx, my):
                    if event.button == 1:
                        ed.place(mx, my)
                    elif event.button == 3:
                        ed.erase(mx, my)

        # перетаскивание ЛКМ для рисования тайлов
        buttons = pygame.mouse.get_pressed(3)
        mx, my = pygame.mouse.get_pos()
        if ed.canvas.collidepoint(mx, my) and ed.mode in ("tiles",):
            if buttons[0]:
                ed.place(mx, my)
            elif buttons[2]:
                ed.erase(mx, my)

        # камера: WASD/стрелки
        keys = pygame.key.get_pressed()
        pan = 360 * dt / ed.zoom
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            ed.cam_x -= pan
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            ed.cam_x += pan
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            ed.cam_y -= pan
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
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

    # старт игрока и конец уровня
    psx, psy = ed.world_to_screen(ed.level["player"]["start_x"], ed.level["player"]["start_y"])
    pygame.draw.rect(screen, (90, 200, 255), (psx - 6, psy - 14, 14, 18), 2)
    screen.blit(font_small.render("START", True, (90, 200, 255)), (psx - 12, psy - 30))
    lex, ley = ed.world_to_screen(ed.level["level_end"]["x"], ed.level["level_end"]["y"])
    screen.blit(am.scaled(am.item("flag"), (size, int(size * 1.6))), (lex, ley - size))
    screen.blit(font_small.render("END", True, (120, 255, 150)), (lex, ley - size - 16))

    # курсор-подсветка
    mx, my = pygame.mouse.get_pos()
    if ed.canvas.collidepoint(mx, my):
        cx, cy = ed.cell_at(mx, my)
        hsx, hsy = ed.world_to_screen(cx * ts, cy * ts)
        pygame.draw.rect(screen, ACCENT, (hsx, hsy, size, size), 2)

    screen.set_clip(prev_clip)

    # --- палитра слева ---
    pygame.draw.rect(screen, PANEL, (0, TOOLBAR_H, PALETTE_W, EDITOR_H - TOOLBAR_H))
    y = TOOLBAR_H + 10
    cat = ed.mode if ed.mode in ed.sel else None
    title = f"Палитра: {ed.mode}"
    screen.blit(font.render(title, True, TEXT), (10, y))
    y += 26
    ids = ed._cat_ids()
    for i, aid in enumerate(ids):
        rect = pygame.Rect(10, y, PALETTE_W - 20, 36)
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
        if y > EDITOR_H - 120:
            break

    # подсказка режимов
    hy = EDITOR_H - 96
    for line in [
        "Колесо — сменить ассет",
        "[ ] кисть  + - зум  G сетка  H хитб.",
        ". , ширина  PgUp/PgDn высота",
        "Ctrl+S save  Ctrl+O load  T тест",
    ]:
        screen.blit(font_small.render(line, True, TEXT_DIM), (10, hy))
        hy += 18

    # --- верхняя панель ---
    pygame.draw.rect(screen, (24, 28, 38), (0, 0, EDITOR_W, TOOLBAR_H))
    info = (
        f"[{MODE_LABELS.get(ed.mode, ed.mode)}]  "
        f"кисть:{ed.brush}  зум:{ed.zoom:.1f}  "
        f"размер:{ed.level['width_tiles']}x{ed.level['height_tiles']}  "
        f"имя:{ed.level.get('name','')}"
    )
    screen.blit(font.render(info, True, TEXT), (10, 10))
    msg = font_small.render(ed.message, True, ACCENT)
    screen.blit(msg, (EDITOR_W - msg.get_width() - 10, 13))


if __name__ == "__main__":
    run_editor()
