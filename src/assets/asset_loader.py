"""
Загрузчик ассетов: PNG → pygame.Surface, с кэшем, целочисленным масштабом
и fallback'ом на «MISSING»-плейсхолдер при отсутствии файла.

Физику этот модуль не трогает — только визуальный слой.
"""

from __future__ import annotations

from pathlib import Path

import pygame

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ASSETS_DIR = BASE_DIR / "assets"

_image_cache: dict[tuple[str, int], pygame.Surface] = {}
_missing_warned: set[str] = set()


def _warn_missing(path: str) -> None:
    if path not in _missing_warned:
        _missing_warned.add(path)
        print(f"[assets] WARNING: ассет не найден: {path} → fallback MISSING")


def get_missing_asset_surface(width: int, height: int) -> pygame.Surface:
    """Заметный fallback: фиолетово-чёрная шахматка."""
    surf = pygame.Surface((max(1, width), max(1, height)), pygame.SRCALPHA)
    cell = max(4, min(width, height) // 4)
    for y in range(0, height, cell):
        for x in range(0, width, cell):
            on = ((x // cell) + (y // cell)) % 2 == 0
            color = (255, 0, 220) if on else (20, 20, 20)
            pygame.draw.rect(surf, color, (x, y, cell, cell))
    return surf


def load_image(relative_path: str, scale: int = 1) -> pygame.Surface:
    """Загрузить PNG (с кэшем). scale — целочисленный множитель (nearest)."""
    scale = max(1, int(scale))
    key = (relative_path, scale)
    cached = _image_cache.get(key)
    if cached is not None:
        return cached

    full = ASSETS_DIR / relative_path
    try:
        img = pygame.image.load(str(full))
        img = img.convert_alpha() if pygame.display.get_surface() else img.convert_alpha()
    except (pygame.error, FileNotFoundError):
        _warn_missing(relative_path)
        img = get_missing_asset_surface(16 * scale, 16 * scale)
        _image_cache[key] = img
        return img

    if scale != 1:
        w, h = img.get_width() * scale, img.get_height() * scale
        img = pygame.transform.scale(img, (w, h))  # nearest — пиксель-арт остаётся чётким
    _image_cache[key] = img
    return img


def load_frames(folder: str, scale: int = 1, sort: bool = True) -> list[pygame.Surface]:
    """Загрузить все PNG из папки как кадры анимации."""
    dir_path = ASSETS_DIR / folder
    if not dir_path.is_dir():
        _warn_missing(folder + "/")
        return [get_missing_asset_surface(16 * scale, 16 * scale)]
    files = [p for p in dir_path.iterdir() if p.suffix.lower() == ".png"]
    if sort:
        files.sort(key=lambda p: p.name)
    frames = [load_image(str(p.relative_to(ASSETS_DIR)), scale) for p in files]
    return frames or [get_missing_asset_surface(16 * scale, 16 * scale)]


def scale_to(surface: pygame.Surface, size: tuple[int, int]) -> pygame.Surface:
    """Растянуть спрайт под точный размер (хитбокс). Кэшируется по id+size."""
    w, h = max(1, int(size[0])), max(1, int(size[1]))
    if surface.get_width() == w and surface.get_height() == h:
        return surface
    return pygame.transform.scale(surface, (w, h))


def clear_cache() -> None:
    _image_cache.clear()
