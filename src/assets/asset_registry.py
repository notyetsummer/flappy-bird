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

def _player_skin_paths(
    folder: str,
    *,
    multi_jump: bool = False,
    death_frames: int = 8,
) -> dict[str, list[str]]:
    """Пути кадров игрока внутри assets/player/ или assets/player/<folder>/."""
    base = f"player/{folder}" if folder else "player"
    jump = (
        [f"{base}/jump_{i}.png" for i in range(4)]
        if multi_jump
        else [f"{base}/jump.png"]
    )
    fall = (
        [f"{base}/fall_{i}.png" for i in range(4)]
        if multi_jump
        else [f"{base}/fall.png"]
    )
    return {
        "idle": [f"{base}/idle_{i}.png" for i in range(4)],
        "run": [f"{base}/run_{i}.png" for i in range(6)],
        "jump": jump,
        "fall": fall,
        "death": [f"{base}/death_{i}.png" for i in range(death_frames)],
    }


# Скин по умолчанию для встроенных уровней и уровней без asset_set
DEFAULT_PLAYER_SKIN = "pink_monster"

# Скины игрока: id → состояния анимации → файлы (относительно assets/)
PLAYER_SKINS: dict[str, dict[str, list[str]]] = {
    "default_player": _player_skin_paths("", multi_jump=False),
    "pink_monster": _player_skin_paths("pink_monster", multi_jump=True),
    "owlet_monster": _player_skin_paths("owlet_monster", multi_jump=True),
    "dude_monster": _player_skin_paths("dude_monster", multi_jump=True),
}

# Соответствия сущность → путь(и) ассета (относительно assets/)
ASSETS: dict[str, dict] = {
    "player": PLAYER_SKINS[DEFAULT_PLAYER_SKIN],
    "tiles": {
        "ground": "tiles/ground.png",
        "grass": "tiles/grass.png",
        "stone": "tiles/stone.png",
        "dirt": "tiles/dirt.png",
    },
    "enemies": {
        "slime": {"idle": [f"enemies/slime_idle_{i}.png" for i in range(4)]},
    },
    "items": {
        "coin": [f"items/coin_{i}.png" for i in range(4)],
        "gem": [f"items/gem_{i}.png" for i in range(4)],
        "key": ["items/key.png"],
        "flag": ["items/flag.png"],
    },
    "obstacles": {
        "spikes": "obstacles/spikes.png",
        "saw": "obstacles/saw.png",
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
    def player_frames(self, state: str, skin: str | None = None) -> list[pygame.Surface]:
        skin = skin or DEFAULT_PLAYER_SKIN
        spec = PLAYER_SKINS.get(skin) or PLAYER_SKINS[DEFAULT_PLAYER_SKIN]
        paths = spec.get(state) or spec["idle"]
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
