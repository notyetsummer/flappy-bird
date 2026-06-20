"""
Импорт спрайтов персонажа из набора Craftpix Tiny Hero Monsters.

Нарезает горизонтальные sprite sheet'ы на отдельные кадры и кладёт их в
assets/player/<skin_id>/ в формате, который понимает asset_registry.py.

Запуск:
    python scripts/import_craftpix_player.py
    python scripts/import_craftpix_player.py --source "/path/to/craftpix-net-..."
    python scripts/import_craftpix_player.py --skin pink_monster
"""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent
ASSETS = BASE_DIR / "assets"
DEFAULT_SOURCE = Path(
    "/Users/admin/Downloads/craftpix-net-622999-free-pixel-art-tiny-hero-sprites"
)

# Папка в архиве Craftpix → id скина в игре
CRAFTPIX_SKINS: dict[str, str] = {
    "1 Pink_Monster": "pink_monster",
    "2 Owlet_Monster": "owlet_monster",
    "3 Dude_Monster": "dude_monster",
}


def _prefix_from_folder(folder_name: str) -> str:
    # "1 Pink_Monster" → "Pink_Monster"
    return folder_name.split(" ", 1)[1].replace(" ", "_")


def _slice_sheet(sheet: pygame.Surface, frame_w: int) -> list[pygame.Surface]:
    w, h = sheet.get_size()
    if w % frame_w != 0:
        raise ValueError(f"ширина {w} не делится на кадр {frame_w}px")
    frames: list[pygame.Surface] = []
    for x in range(0, w, frame_w):
        frame = pygame.Surface((frame_w, h), pygame.SRCALPHA)
        frame.blit(sheet, (0, 0), pygame.Rect(x, 0, frame_w, h))
        frames.append(frame)
    return frames


def _save_frames(frames: list[pygame.Surface], out_dir: Path, prefix: str) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    for i, frame in enumerate(frames):
        rel = f"player/{out_dir.name}/{prefix}_{i}.png"
        path = ASSETS / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        pygame.image.save(frame, str(path))
        created.append(rel)
    return created


def import_skin(source_dir: Path, folder_name: str, skin_id: str) -> list[str]:
    src = source_dir / folder_name
    if not src.is_dir():
        raise FileNotFoundError(f"папка скина не найдена: {src}")

    prefix = _prefix_from_folder(folder_name)
    out_dir = ASSETS / "player" / skin_id
    created: list[str] = []

    idle_sheet = src / f"{prefix}_Idle_4.png"
    run_sheet = src / f"{prefix}_Run_6.png"
    jump_sheet = src / f"{prefix}_Jump_8.png"
    death_sheet = src / f"{prefix}_Death_8.png"

    for path in (idle_sheet, run_sheet, jump_sheet, death_sheet):
        if not path.is_file():
            raise FileNotFoundError(f"ожидался файл анимации: {path}")

    idle_frames = _slice_sheet(pygame.image.load(str(idle_sheet)), 32)
    run_frames = _slice_sheet(pygame.image.load(str(run_sheet)), 32)
    jump_frames = _slice_sheet(pygame.image.load(str(jump_sheet)), 32)
    death_frames = _slice_sheet(pygame.image.load(str(death_sheet)), 32)

    created.extend(_save_frames(idle_frames, out_dir, "idle"))
    created.extend(_save_frames(run_frames, out_dir, "run"))
    # прыжок: первые 4 кадра; падение: последние 4
    created.extend(_save_frames(jump_frames[:4], out_dir, "jump"))
    created.extend(_save_frames(jump_frames[4:], out_dir, "fall"))
    created.extend(_save_frames(death_frames, out_dir, "death"))

    return created


def write_license_note(skin_ids: list[str]) -> None:
    md = ASSETS / "licenses" / "asset_sources.md"
    block = (
        "\n\n## Craftpix — Tiny Hero Monsters\n\n"
        "- Source: Craftpix.net (free pixel art tiny hero sprites)\n"
        "- License: https://craftpix.net/file-licenses/\n"
        "- Usage status: integrated (player skins)\n"
        f"- Skins: {', '.join(skin_ids)}\n"
        "- Import: `python scripts/import_craftpix_player.py`\n"
    )
    md.parent.mkdir(parents=True, exist_ok=True)
    if md.is_file():
        text = md.read_text(encoding="utf-8")
        if "Craftpix — Tiny Hero Monsters" not in text:
            md.write_text(text + block, encoding="utf-8")
    else:
        md.write_text("# Источники ассетов" + block, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Импорт Craftpix player skins")
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help="папка с распакованным архивом Craftpix",
    )
    parser.add_argument(
        "--skin",
        choices=list(CRAFTPIX_SKINS.values()),
        help="импортировать только один скин",
    )
    args = parser.parse_args()

    pygame.init()
    source = args.source.expanduser().resolve()
    if not source.is_dir():
        raise SystemExit(f"Источник не найден: {source}")

    raw = ASSETS / "raw_downloads" / "craftpix-tiny-hero-monsters"
    if not raw.exists():
        raw.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, raw, dirs_exist_ok=True)

    targets = CRAFTPIX_SKINS.items()
    if args.skin:
        targets = [(k, v) for k, v in CRAFTPIX_SKINS.items() if v == args.skin]

    all_created: list[str] = []
    imported: list[str] = []
    for folder, skin_id in targets:
        print(f"[craftpix] импорт {skin_id} …")
        created = import_skin(source, folder, skin_id)
        all_created.extend(created)
        imported.append(skin_id)
        print(f"[craftpix]   → {len(created)} файлов")

    write_license_note(imported)
    print(f"[craftpix] Готово: {len(all_created)} PNG в assets/player/")


if __name__ == "__main__":
    main()
