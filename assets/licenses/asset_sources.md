# Источники ассетов

## Generated Pixel Placeholder Pack

- Source: сгенерировано scripts/setup_assets.py (этот проект)
- Author: проект (procedural)
- License: CC0 / Public Domain
- Usage status: integrated
- Notes: базовый набор спрайтов (игрок, тайлы, монета, шипы, слайм, фон, флаг, UI). Создан кодом, поэтому свободен от лицензионных рисков.

## Как заменить на ассеты Kenney (опционально, выше качеством)

1. Скачай вручную CC0-набор, например Kenney Pixel Platformer:
   https://kenney.nl/assets/pixel-platformer
2. Положи архив в `assets/raw_downloads/` и распакуй.
3. Скопируй нужные PNG в рабочие папки `assets/player`, `assets/tiles`, `assets/items`, `assets/enemies`, `assets/obstacles`, `assets/backgrounds`, сохранив имена файлов из `src/assets/asset_registry.py` (или поправь пути в реестре).
4. Добавь запись об источнике и лицензии Kenney (CC0) в этот файл и в `licenses.json`.

Не используй ассеты с пометками personal-use-only / no-commercial / требующие покупки. При неясной лицензии — пропусти ассет.
