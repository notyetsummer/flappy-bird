"""
Реестр ассетов: соответствие игровых сущностей и файлов спрайтов,
плюс высокоуровневый AssetManager с кэшем готовых поверхностей.

При отсутствии файлов всё деградирует на fallback (см. asset_loader), игра
не падает. Если ассеты вообще не сгенерированы — игра рисует примитивы
(вызывающая сторона сама решает по AssetManager.available).
"""

from __future__ import annotations

import pygame

from . import asset_loader

# Соответствия сущность → путь(и) ассета (относительно assets/)
ASSETS: dict[str, dict] = {
    "player": {
        "idle": ["player/idle_0.png", "player/idle_1.png"],
        "run": ["player/run_0.png", "player/run_1.png", "player/run_2.png", "player/run_3.png"],
        "jump": ["player/jump.png"],
        "fall": ["player/fall.png"],
    },
    "tiles": {
        "ground": "tiles/ground.png",
        "grass": "tiles/grass.png",
        "stone": "tiles/stone.png",
        "dirt": "tiles/dirt.png",
    },
    "enemies": {
        "slime": {"idle": ["enemies/slime_idle_0.png", "enemies/slime_idle_1.png"]},
    },
    "items": {
        "coin": ["items/coin_0.png", "items/coin_1.png", "items/coin_2.png", "items/coin_3.png"],
        "flag": ["items/flag.png"],
    },
    "obstacles": {
        "spikes": "obstacles/spikes.png",
    },
    "backgrounds": {
        "default": "backgrounds/default.png",
    },
    "ui": {
        "heart_full": "ui/heart_full.png",
        "heart_empty": "ui/heart_empty.png",
    },
}

# Каталоги для палитры редактора: (категория, id, путь-превью)
TILE_IDS = list(ASSETS["tiles"].keys())
ITEM_IDS = list(ASSETS["items"].keys())
ENEMY_IDS = list(ASSETS["enemies"].keys())
OBSTACLE_IDS = list(ASSETS["obstacles"].keys())
BACKGROUND_IDS = list(ASSETS["backgrounds"].keys())


class AssetManager:
    """Единая точка доступа к спрайтам для игры и редактора."""

    def __init__(self) -> None:
        self.available = asset_loader.ASSETS_DIR.is_dir()
        self._frames: dict[str, list[pygame.Surface]] = {}
        self._single: dict[str, pygame.Surface] = {}

    # --- низкоуровневое ---
    def frames(self, paths: list[str]) -> list[pygame.Surface]:
        key = "|".join(paths)
        cached = self._frames.get(key)
        if cached is None:
            cached = [asset_loader.load_image(p) for p in paths]
            self._frames[key] = cached
        return cached

    def single(self, path: str) -> pygame.Surface:
        cached = self._single.get(path)
        if cached is None:
            cached = asset_loader.load_image(path)
            self._single[path] = cached
        return cached

    # --- удобные геттеры по реестру ---
    def player_frames(self, state: str) -> list[pygame.Surface]:
        paths = ASSETS["player"].get(state) or ASSETS["player"]["idle"]
        return self.frames(paths)

    def tile(self, tile_id: str) -> pygame.Surface:
        path = ASSETS["tiles"].get(tile_id, ASSETS["tiles"]["ground"])
        return self.single(path)

    def coin_frames(self) -> list[pygame.Surface]:
        return self.frames(ASSETS["items"]["coin"])

    def item(self, item_id: str) -> pygame.Surface:
        paths = ASSETS["items"].get(item_id)
        if isinstance(paths, list):
            return self.frames(paths)[0]
        return self.single(paths) if paths else asset_loader.get_missing_asset_surface(16, 16)

    def obstacle(self, obstacle_id: str) -> pygame.Surface:
        path = ASSETS["obstacles"].get(obstacle_id, ASSETS["obstacles"]["spikes"])
        return self.single(path)

    def enemy_frames(self, enemy_id: str, anim: str = "idle") -> list[pygame.Surface]:
        spec = ASSETS["enemies"].get(enemy_id, ASSETS["enemies"]["slime"])
        paths = spec.get(anim) or next(iter(spec.values()))
        return self.frames(paths)

    def background(self, bg_id: str) -> pygame.Surface:
        path = ASSETS["backgrounds"].get(bg_id, ASSETS["backgrounds"]["default"])
        return self.single(path)

    def scaled(self, surface: pygame.Surface, size: tuple[int, int]) -> pygame.Surface:
        return asset_loader.scale_to(surface, size)


_manager: AssetManager | None = None


def get_asset_manager() -> AssetManager:
    global _manager
    if _manager is None:
        _manager = AssetManager()
    return _manager
