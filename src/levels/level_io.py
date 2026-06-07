"""
Чтение/запись уровней в JSON и конвертация в игровой LevelData.

JSON-схема (см. ТЗ §5.8): сетка тайлов (grid) + свободные объекты
(платформы, враги, предметы, препятствия, старт игрока, конец уровня).

Физику не трогаем: на выходе получаем привычный platformer.LevelData
с RectObj-хитбоксами, который проигрывает существующий движок.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent.parent
LEVELS_DIR = BASE_DIR / "levels"
SCREEN_H = 540  # движок скроллит только по X; высота сцены = высоте экрана

DEFAULT_TILE_SIZE = 48
SCHEMA_VERSION = 1


def new_level(name: str = "untitled", width_tiles: int = 60, height_tiles: int = 11,
              tile_size: int = DEFAULT_TILE_SIZE) -> dict[str, Any]:
    """Пустой шаблон уровня."""
    return {
        "version": SCHEMA_VERSION,
        "name": name,
        "tile_size": tile_size,
        "width_tiles": width_tiles,
        "height_tiles": height_tiles,
        "background": "default",
        "player": {"start_x": tile_size * 2, "start_y": SCREEN_H - tile_size - 40,
                   "asset_set": "default_player"},
        "level_end": {"x": (width_tiles - 3) * tile_size, "y": SCREEN_H - tile_size - 70,
                      "type": "flag"},
        "tiles": [],
        "platforms": [],
        "enemies": [],
        "items": [],
        "obstacles": [],
        "decorations": [],
    }


def save_level(level: dict[str, Any], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(level, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_level_file(path: str | Path) -> dict[str, Any]:
    """Загрузить и проверить JSON-уровень. Бросает ValueError при проблеме."""
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"Файл уровня не найден: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Повреждён JSON уровня {path}: {e}") from e
    return _normalize(data)


def _normalize(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Уровень должен быть JSON-объектом")
    base = new_level()
    base.update({k: v for k, v in data.items() if v is not None})
    # гарантируем наличие списков
    for key in ("tiles", "platforms", "enemies", "items", "obstacles", "decorations"):
        if not isinstance(base.get(key), list):
            base[key] = []
    base["tile_size"] = int(base.get("tile_size", DEFAULT_TILE_SIZE))
    base["width_tiles"] = int(base.get("width_tiles", 60))
    base["height_tiles"] = int(base.get("height_tiles", 11))
    return base


def dict_to_leveldata(level: dict[str, Any]):
    """Сконвертировать JSON-уровень в platformer.LevelData (ленивый импорт)."""
    import platformer as P  # ленивый импорт, чтобы избежать циклов

    level = _normalize(level)
    ts = level["tile_size"]
    world_w = max(P.W, level["width_tiles"] * ts)

    platforms: list = []
    # сетка тайлов → твёрдые квадраты
    for t in level["tiles"]:
        platforms.append(P.RectObj(t["x"] * ts, t["y"] * ts, ts, ts,
                                   tile_id=t.get("tile_id", "ground")))
    # свободные платформы (в пикселях)
    for pl in level["platforms"]:
        platforms.append(P.RectObj(pl["x"], pl["y"], pl["width"], pl["height"],
                                   tile_id=pl.get("tile_id", "grass")))

    spikes: list = []
    for ob in level["obstacles"]:
        w = ob.get("width", ts)
        h = ob.get("height", ts)
        spikes.append(P.RectObj(ob["x"], ob["y"], w, h,
                                tile_id=ob.get("asset_id", "spikes")))

    coins: list = []
    for it in level["items"]:
        coins.append(P.CoinObj(it["x"], it["y"]))

    enemies: list = []
    for en in level["enemies"]:
        props = en.get("properties", {}) or {}
        enemies.append(P.Enemy(
            x=en["x"], y=en["y"],
            enemy_type=en.get("enemy_type", "slime"),
            asset_id=en.get("asset_id", en.get("enemy_type", "slime")),
            patrol_left=props.get("patrol_left", en["x"] - 80),
            patrol_right=props.get("patrol_right", en["x"] + 80),
        ))

    end = level["level_end"]
    goal = P.RectObj(end["x"], end["y"], 40, 70, tile_id="flag")

    player = level["player"]
    spawn = (float(player["start_x"]), float(player["start_y"]))

    return P.LevelData(
        name=level.get("name", "JSON level"),
        world_w=int(world_w),
        spawn=spawn,
        platforms=platforms,
        spikes=spikes,
        coins=coins,
        enemies=enemies,
        goal=goal,
        background=level.get("background", "default"),
    )


def sample_level() -> dict[str, Any]:
    """Демо-уровень для levels/level_001.json."""
    ts = DEFAULT_TILE_SIZE
    lvl = new_level("level_001", width_tiles=40, height_tiles=11, tile_size=ts)
    ground_row = 10
    # сплошная земля
    for x in range(0, 40):
        if x in (14, 15, 24, 25):  # пара ям
            continue
        lvl["tiles"].append({"x": x, "y": ground_row, "tile_id": "grass"})
    # парящие платформы
    lvl["platforms"].append({"x": 6 * ts, "y": ground_row * ts - 130, "width": 3 * ts,
                             "height": 24, "tile_id": "stone"})
    lvl["platforms"].append({"x": 18 * ts, "y": ground_row * ts - 170, "width": 3 * ts,
                             "height": 24, "tile_id": "stone"})
    # монеты
    for cx in (3, 7, 8, 19, 20, 30):
        lvl["items"].append({"x": cx * ts + ts // 2, "y": ground_row * ts - 60,
                             "item_type": "coin", "asset_id": "coin"})
    # шипы в ямах
    for x in (14, 15, 24, 25):
        lvl["obstacles"].append({"x": x * ts, "y": ground_row * ts + ts - 18,
                                 "width": ts, "height": 18,
                                 "obstacle_type": "spikes", "asset_id": "spikes"})
    # враг
    lvl["enemies"].append({"x": 22 * ts, "y": ground_row * ts - 30,
                           "enemy_type": "slime", "asset_id": "slime",
                           "properties": {"patrol_left": 21 * ts, "patrol_right": 23 * ts}})
    lvl["player"]["start_x"] = ts
    lvl["player"]["start_y"] = ground_row * ts - 40
    lvl["level_end"] = {"x": 37 * ts, "y": ground_row * ts - 70, "type": "flag"}
    return lvl
