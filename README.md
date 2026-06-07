# Pygame платформер + Flappy Bird

Сборник из двух игр на **Python + pygame**: платформер (с уровнями, редактором и
пиксель-арт ассетами) и улучшенный Flappy Bird. Запуск из корня проекта.

## Установка

```bash
python3 -m pip install -r requirements.txt
```

## Установка ассетов

Базовый набор пиксель-арт ассетов (CC0) генерируется скриптом:

```bash
python3 scripts/setup_assets.py
```

Ассеты складываются в `assets/`. Если их нет — игра не падает, а рисует
примитивы (fallback). Подробнее об источниках и о замене на наборы Kenney —
см. `assets/licenses/asset_sources.md`.

## Запуск игры

```bash
python3 main.py
```

Откроется меню выбора уровней (стрелки/`WASD` + `Enter`, либо цифры `1–5`).

## Запуск конкретного уровня

```bash
python3 main.py --level levels/level_001.json
```

## Запуск редактора

```bash
python3 main.py --editor
```

Редактор уровней (чистый pygame). Управление:

| Клавиша | Действие |
|---|---|
| `1`–`9`, `0` | режимы: tiles / platforms / enemies / items / obstacles / player start / level end / select / background / test |
| ЛКМ / ПКМ | поставить / удалить объект |
| колесо мыши | сменить ассет в текущей категории |
| `WASD` / стрелки | двигать камеру |
| `+` / `-` | зум, `[` / `]` — размер кисти |
| `.` / `,` | ширина уровня, `PgUp` / `PgDn` — высота |
| `G` / `H` | сетка / хитбоксы |
| `Ctrl+S` / `Ctrl+O` | сохранить / загрузить (`levels/<имя>.json`) |
| `T` | playtest текущего уровня (выход назад — `Esc`) |
| `Esc` | выйти из редактора |

## Отладка хитбоксов

```bash
python3 main.py --debug-hitboxes
```

## Flappy Bird (отдельный хаб-меню с двумя играми)

```bash
python3 "Export_Version_2 (2).py"
```

В имени файла есть пробелы и скобки — в командной строке берите его в кавычках.

## Лицензии ассетов

См. `assets/licenses/asset_sources.md` и `assets/licenses/licenses.json`.

## Структура

```text
main.py                 # точка входа (--editor / --level / --debug-hitboxes)
platformer.py           # движок и игровая логика (физика на pygame.Rect)
scripts/setup_assets.py # генерация ассетов + файлов лицензий
src/assets/             # asset_loader.py, asset_registry.py
src/levels/level_io.py  # JSON <-> LevelData
src/editor/level_editor.py
assets/                 # спрайты по категориям + licenses/
levels/                 # JSON-уровни (level_001.json — демо)
```

## Зависимости

См. `requirements.txt`: `pygame`, `pygame-menu`.
