import math
import random
import time
from pathlib import Path

import pygame
import pygame_menu

# ---------- paths ----------
BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"


# ---------- Flappy Bird: всё ручное управление геймплеем (редактируйте здесь) ----------
class FlappyTuning:
    """Собранные параметры баланса. Значения ниже — стартовые; подбирайте по вкусу."""

    # Кадры
    TARGET_FPS = 60
    # Логика изначально ориентировалась на ~120 шагов/с: при другом TARGET_FPS масштаб шага.
    STEP_SCALE = 120 / TARGET_FPS

    # Физика птицы (шаг за один кадр при TARGET_FPS; главный рычаг «как тяжело падает»)
    GRAVITY_PER_FRAME = 0.30
    FLAP_IMPULSE = -8.2
    # Усиление гравитации после смерти (дольше «доусыпать» вниз)
    DEATH_GRAVITY_MULT = 0.6
    # Отсечение подъёма при отпускании Space (укороченный взмах). False = все взмахи одной силы.
    SHORT_FLAP_ON_KEYUP = False
    JUMP_CUT_MULT = 0.48
    # Буфер «хочу взмахнуть» до срабатывания (сек)
    INPUT_BUFFER_SEC = 0.12
    # Режим «Сложно»: минимум между двумя взмахами (сек)
    HARD_FLAP_COOLDOWN_SEC = 0.5

    # Двойной прыжок: не скорость, а сдвиг вверх на фиксированное число пикселей
    # от положения в момент нажатия (rect.y меньше = выше на экране).
    DOUBLE_JUMP_COOLDOWN_SEC = 3.0
    DOUBLE_JUMP_RISE_PX = 72

    # Нитро: зажат Space — расход топлива и подъём за кадр; отжал — только обычная физика
    NITRO_MAX_UNITS = 100.0
    NITRO_DRAIN_PER_FRAME = 2.15
    NITRO_LIFT_PER_FRAME = -0.62

    # Сфера-аура в щели между трубами: висит AURA_ORB_HANG_SEC, после сбора — щит AURA_SHIELD_SEC
    AURA_ORB_HANG_SEC = 30.0
    AURA_ORB_RADIUS = 26
    AURA_SHIELD_SEC = 30.0
    # При ударе о трубу под щитом — неуязвимость (проходит сквозь коллизию по трубе)
    AURA_PIPE_INVINCIBLE_SEC = 1.0

    # Препятствия и уровень
    GROUND_HEIGHT = 110
    PIPE_WIDTH = 88
    PIPE_SPACING = 340
    # Диапазон размера щели (пикс.) — чем шире кортеж, тем сильнее разброс высоты столбов
    GAP_EASY = (190, 265)
    GAP_HARD = (160, 220)
    # «Виртуальная» скорость труб (как раньше int() давала шаг в пикселях после STEP_SCALE)
    PIPE_SPEED = 2.8
    # Сдвиг по X при первом спавне труб: width + i*spacing + random
    PIPE_SPAWN_X_JITTER = (0, 80)
    # Новая труба: mx + spacing + random(мин, макс)
    PIPE_RESPAWN_SPACING_EXTRA = (-40, 120)
    # Вертикальные поля — случайная высота щели: меньше = больше амплитуда по Y
    PIPE_GAP_VERTICAL_MARGIN = 150

    # Хитбоксы: пикселей с каждой стороны внутрь (больше число = меньше хитбокс vs спрайт)
    BIRD_HIT_INSET = 9
    PIPE_HIT_INSET = 5

    # Границы полёта птицы
    BIRD_START_X = 220
    CEILING_TOP = -40
    CEILING_HEIGHT = 42
    BIRD_Y_CLAMP_TOP = -30

    # Скорость анимации кадров птицы
    BIRD_ANIM_SPEED = 5
    BIRD_SPRITE_SIZE = (56, 42)

    # Эффекты
    SHAKE_ON_DEATH = 14.0
    SHAKE_DECAY = 0.88
    DEATH_TILT_SPEED = 400.0
    DEATH_TILT_MAX = 75.0

    def pipe_dx(self):
        """Пикселей сдвига труб за кадр (целое)."""
        return max(1, int(int(self.PIPE_SPEED) * self.STEP_SCALE))

    def scroll_step(self):
        """Прокрутка земли за кадр (как раньше, согласовано с трубами)."""
        return float(int(self.PIPE_SPEED)) * self.STEP_SCALE


TUNING = FlappyTuning()


size = (1200, 800)
width, height = size
name = ["John Doe"]
difficulty = [1]

# Опции раунда (меняются в меню до «Играть»)
opt_enable_nitro = [True]
opt_enable_shield = [True]
opt_enable_double_jump = [True]


def set_difficulty(_, y):
    difficulty.append(y)


def set_opt_nitro(_, value):
    opt_enable_nitro[0] = value


def set_opt_shield(_, value):
    opt_enable_shield[0] = value


def set_opt_double_jump(_, value):
    opt_enable_double_jump[0] = value


def MyTextValue(Player_name):
    name.append(str(Player_name))


def read_results():
    path = BASE_DIR / "Results.txt"
    if not path.exists():
        return ["—"] * 6
    try:
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return ["—"] * 6
        parts = [p.strip() for p in text.split(",") if p.strip()]
        leaders = sorted(parts, reverse=True)
    except OSError:
        leaders = []
    while len(leaders) < 6:
        leaders.append("—")
    return leaders[:6]


def _try_load_images(patterns):
    surfaces = []
    for p in patterns:
        path = Path(p)
        if path.is_file():
            try:
                surfaces.append(pygame.image.load(str(path)).convert_alpha())
            except pygame.error:
                pass
    return surfaces


def load_bird_frames(target_size):
    """Frames from assets/bird/frame_*.png, or user Downloads, else procedural."""
    frames = []
    bird_dir = ASSETS_DIR / "bird"
    if bird_dir.is_dir():
        for i in range(1, 10):
            f = bird_dir / f"frame_{i}.png"
            if f.is_file():
                img = pygame.image.load(str(f)).convert_alpha()
                frames.append(pygame.transform.smoothscale(img, target_size))

    if not frames:
        legacy = [
            Path.home() / "Downloads" / f"frame_{i}.png" for i in range(1, 7)
        ]
        frames = _try_load_images(legacy)

    if not frames:
        w, h = target_size
        for wing in range(4):
            surf = pygame.Surface((w, h), pygame.SRCALPHA)
            body = pygame.Rect(int(w * 0.15), int(h * 0.25), int(w * 0.65), int(h * 0.5))
            pygame.draw.ellipse(surf, (250, 220, 80), body)
            pygame.draw.ellipse(surf, (230, 190, 50), body, 2)
            eye = (int(w * 0.62), int(h * 0.42))
            pygame.draw.circle(surf, (255, 255, 255), eye, max(4, h // 10))
            pygame.draw.circle(surf, (40, 40, 40), (eye[0] + 1, eye[1]), max(2, h // 18))
            beak_pts = [
                (w - 4, int(h * 0.48)),
                (w + int(w * 0.12), int(h * 0.52)),
                (w - 2, int(h * 0.58)),
            ]
            pygame.draw.polygon(surf, (235, 120, 60), beak_pts)
            wing_angle = wing * 18 - 27
            wing_s = pygame.Surface((int(w * 0.38), int(h * 0.38)), pygame.SRCALPHA)
            pygame.draw.ellipse(wing_s, (255, 200, 70), wing_s.get_rect())
            wing_s = pygame.transform.rotate(wing_s, wing_angle)
            surf.blit(wing_s, (int(w * 0.1), int(h * 0.32)))
            frames.append(surf)

    out = []
    for im in frames:
        out.append(pygame.transform.smoothscale(im, target_size))
    return out


def draw_nitro_bar(surface, x, y, w, h, frac):
    frac = max(0.0, min(1.0, frac))
    bg = (40, 50, 70)
    fill = (255, 120, 40) if frac < 0.25 else (80, 200, 255)
    pygame.draw.rect(surface, bg, (x, y, w, h), border_radius=4)
    if frac > 0:
        pygame.draw.rect(surface, fill, (x + 2, y + 2, int((w - 4) * frac), h - 4), border_radius=3)


def draw_gap_aura_orb(surface, cx, cy, r, pulse_t):
    d = max(r * 2 + 18, 32)
    s = pygame.Surface((d, d), pygame.SRCALPHA)
    pr = max(8, int(r + 5 * math.sin(pulse_t * 4)))
    ctr = (d // 2, d // 2)
    pygame.draw.circle(s, (100, 220, 255, 70), ctr, pr)
    pygame.draw.circle(s, (200, 255, 255, 160), ctr, max(6, pr - 6), width=4)
    pygame.draw.circle(s, (255, 255, 255, 220), ctr, max(4, pr - 14), width=2)
    surface.blit(s, (int(cx - d // 2), int(cy - d // 2)))


def draw_shield_overlay(surface, br, blink_on, t):
    """Кольца вокруг птицы: щит (голубое) или мигание при короткой неуязвимости."""
    ctr = br.center
    r = max(br.width, br.height) // 2 + 12
    a = min(210, int(140 + 70 * math.sin(t * 6))) if blink_on else 165
    s = pygame.Surface((br.width + 56, br.height + 56), pygame.SRCALPHA)
    c0 = (s.get_width() // 2, s.get_height() // 2)
    pygame.draw.circle(s, (80, 220, 255, a), c0, r, width=3)
    pygame.draw.circle(s, (255, 255, 255, min(a, 90)), c0, r - 5, width=2)
    surface.blit(s, (br.centerx - c0[0], br.centery - c0[1]))


def draw_gradient_sky(surface, t):
    top = (120 + int(15 * math.sin(t * 0.15)), 185 + int(10 * math.cos(t * 0.12)), 230)
    mid = (170 + int(10 * math.sin(t * 0.2)), 215, 235)
    bot = (235, 245, 255)
    for y in range(height):
        k = y / height
        if k < 0.55:
            u = k / 0.55
            col = tuple(int(top[i] + (mid[i] - top[i]) * u) for i in range(3))
        else:
            u = (k - 0.55) / 0.45
            col = tuple(int(mid[i] + (bot[i] - mid[i]) * u) for i in range(3))
        pygame.draw.line(surface, col, (0, y), (width, y))


def init_clouds():
    clouds = []
    for _ in range(14):
        clouds.append(
            {
                "x": random.uniform(-200, width + 200),
                "y": random.randint(40, height // 2 + 120),
                "r": random.randint(38, 95),
                "speed": random.uniform(0.15, 0.85),
                "layer": random.randint(0, 2),
                "phase": random.uniform(0, math.tau),
            }
        )
    return clouds


def update_clouds(clouds, dt):
    for c in clouds:
        layer_mul = 0.35 + c["layer"] * 0.35
        c["x"] -= c["speed"] * layer_mul * dt * 60
        if c["x"] < -c["r"] * 3:
            c["x"] = width + c["r"] * 2 + random.randint(0, 200)
            c["y"] = random.randint(40, height // 2 + 140)


def draw_cloud(surface, cx, cy, r, alpha):
    layers = [(r, alpha), (int(r * 0.72), alpha - 25), (int(r * 0.55), alpha - 45)]
    for rad, al in layers:
        if al <= 8:
            continue
        s = pygame.Surface((rad * 4, rad * 3), pygame.SRCALPHA)
        pygame.draw.circle(s, (255, 255, 255, al), (rad, int(rad * 1.2)), rad)
        pygame.draw.circle(s, (255, 255, 255, al), (rad * 2, int(rad * 1.1)), int(rad * 0.92))
        pygame.draw.circle(s, (255, 255, 255, al), (rad * 3, int(rad * 1.25)), int(rad * 0.85))
        surface.blit(s, (int(cx - rad * 2), int(cy - rad)))


def draw_clouds(surface, clouds, t):
    ordered = sorted(clouds, key=lambda c: c["layer"])
    for c in ordered:
        bob = 4 * math.sin(t * 0.8 + c["phase"])
        base_alpha = 55 + c["layer"] * 35
        draw_cloud(surface, c["x"], c["y"] + bob, c["r"], min(220, base_alpha + 40))


def init_wind_particles():
    parts = []
    for _ in range(42):
        parts.append(
            {
                "x": random.uniform(0, width),
                "y": random.randint(int(height * 0.35), height - 140),
                "vx": random.uniform(2.5, 7.5),
                "len": random.randint(14, 44),
                "wobble": random.uniform(0, math.tau),
                "thick": random.randint(1, 2),
                "alpha": random.randint(35, 95),
            }
        )
    return parts


def update_wind(parts, dt):
    for p in parts:
        p["x"] += p["vx"] * dt * 60
        p["wobble"] += dt * 4
        if p["x"] > width + 80:
            p["x"] = random.uniform(-120, -20)
            p["y"] = random.randint(int(height * 0.3), height - 160)


def draw_wind(surface, parts, t):
    wsurf = pygame.Surface((width, height), pygame.SRCALPHA)
    for p in parts:
        wy = p["y"] + 6 * math.sin(p["wobble"] + t * 3)
        x1, x2 = p["x"], p["x"] - p["len"]
        bend = 10 * math.sin(t * 2 + p["wobble"])
        pts = [
            (x2, wy + bend * 0.3),
            (x1, wy),
            (x2, wy - bend * 0.25),
        ]
        col = (245, 250, 255, min(140, p["alpha"] + int(25 * math.sin(t + p["wobble"]))))
        pygame.draw.lines(wsurf, col, False, pts, p["thick"])
    surface.blit(wsurf, (0, 0))


def draw_grass_strip(surface, scroll, t, ground_top):
    blade_count = int(width / 10) + 3
    for i in range(blade_count):
        bx = i * 11 - int(scroll * 0.8) % 110 - 15
        sway = (
            10 * math.sin(t * 2.2 + bx * 0.03)
            + 6 * math.sin(t * 3.5 + bx * 0.07 + 1.7)
        )
        tip_x = bx + sway
        tip_y = ground_top - (18 + (i * 13) % 17)
        hue_shift = int(18 * math.sin(t + bx * 0.05))
        green = (56 + hue_shift, 160 + hue_shift // 2, 72 + hue_shift // 3)
        pygame.draw.lines(surface, green, False, [(bx, ground_top), (tip_x, tip_y)], 2)


def draw_ground(surface, scroll, t, ground_h):
    top_y = height - ground_h
    soil_dark = (92, 62, 42)
    soil = (135, 92, 58)
    pygame.draw.rect(surface, soil_dark, (0, top_y + 28, width, ground_h))
    pygame.draw.rect(surface, soil, (0, top_y + 18, width, 35))
    stripe_phase = scroll % 120
    for x in range(-120, width + 120, 60):
        pygame.draw.rect(surface, (120, 82, 52), (x - stripe_phase, top_y + 40, 28, ground_h))
    grass_top = top_y + 18
    pygame.draw.rect(surface, (74, 168, 88), (0, grass_top - 6, width, 28))
    draw_grass_strip(surface, scroll, t, grass_top + 22)


def draw_pipe(surface, rect, flip=False):
    """Rounded pipe body + cap + shine."""
    x, y, w, h = rect.x, rect.y, rect.width, rect.height
    if h <= 0 or w <= 0:
        return
    body_w = int(w * 0.86)
    inset = (w - body_w) // 2
    cap_h = min(28, max(14, h // 8))
    dark = (35, 110, 48)
    mid = (72, 168, 82)
    light = (118, 212, 130)
    shine = (190, 245, 198)

    inner = pygame.Rect(x + inset, y, body_w, h)
    pygame.draw.rect(surface, dark, inner.inflate(6, 6), border_radius=10)

    steps = max(8, h // 12)
    for s in range(steps):
        ty = y + int(h * s / steps)
        bh = max(1, h // steps + 2)
        band = pygame.Rect(inner.left, ty, inner.width, bh)
        blend = s / max(1, steps - 1)
        c = tuple(int(mid[i] * (1 - blend * 0.25) + light[i] * (blend * 0.25)) for i in range(3))
        pygame.draw.rect(surface, c, band)

    pygame.draw.rect(surface, mid, inner, border_radius=10)
    pygame.draw.rect(surface, dark, inner, width=3, border_radius=10)

    gloss = pygame.Rect(inner.left + 6, inner.top + int(h * 0.08), max(6, body_w // 6), h - cap_h - 18)
    pygame.draw.rect(surface, shine, gloss, border_radius=6)

    if flip:
        cap = pygame.Rect(x, y + h - cap_h, w, cap_h)
    else:
        cap = pygame.Rect(x, y, w, cap_h)
    pygame.draw.rect(surface, light, cap.inflate(-4, 0), border_radius=8)
    pygame.draw.rect(surface, dark, cap.inflate(-4, 0), width=2, border_radius=8)


def spawn_pipe_pair(
    index,
    spacing,
    pipe_w,
    gap_min,
    gap_max,
    ground_h,
    *,
    x_jitter=(0, 80),
    vertical_margin=180,
):
    x = width + index * spacing + random.randint(*x_jitter)
    full_gap = random.randint(gap_min, gap_max)
    gap_half = full_gap // 2
    cy = random.randint(
        vertical_margin + gap_half,
        height - ground_h - vertical_margin - gap_half,
    )
    top_h = cy - gap_half
    bot_top = cy + gap_half
    bot_h = height - ground_h - bot_top
    top_rect = pygame.Rect(x, 0, pipe_w, top_h)
    bot_rect = pygame.Rect(x, bot_top, pipe_w, bot_h)
    return top_rect, bot_rect


def start_the_game():
    tn = TUNING
    enable_nitro = opt_enable_nitro[0]
    enable_shield = opt_enable_shield[0]
    enable_double_jump = opt_enable_double_jump[0]
    clock = pygame.time.Clock()
    ground_h = tn.GROUND_HEIGHT
    pipe_w = tn.PIPE_WIDTH
    spacing = tn.PIPE_SPACING
    gap_easy = tn.GAP_EASY
    gap_hard = tn.GAP_HARD
    pipe_dx = tn.pipe_dx()
    scroll_step = tn.scroll_step()

    gap_rng = gap_hard if difficulty[-1] == 1 else gap_easy
    wall_counter = max(3, int(width / spacing) + 2)

    screen = pygame.display.set_mode(size)
    pygame.display.set_caption("Flappy Bird — улучшенная версия")

    bird_size = tn.BIRD_SPRITE_SIZE
    Player_Sprite = load_bird_frames(bird_size)
    anim_speed = tn.BIRD_ANIM_SPEED

    clouds = init_clouds()
    wind_parts = init_wind_particles()

    list_wall = []
    list_wall2 = []
    pipe_passed = []
    for i in range(wall_counter):
        tr, br = spawn_pipe_pair(
            i,
            spacing,
            pipe_w,
            gap_rng[0],
            gap_rng[1],
            ground_h,
            x_jitter=tn.PIPE_SPAWN_X_JITTER,
            vertical_margin=tn.PIPE_GAP_VERTICAL_MARGIN,
        )
        list_wall2.append(tr)
        list_wall.append(br)
        pipe_passed.append(False)

    # Сферы ауры привязаны к индексу пары труб: expire — абсолютное game_time, collected — подобрана
    aura_orbs = []
    for _i in range(wall_counter):
        aura_orbs.append(
            {"expire_at": tn.AURA_ORB_HANG_SEC, "collected": False},
        )

    nitro_fuel = tn.NITRO_MAX_UNITS
    shield_until_gt = -1.0
    invuln_until_gt = -1.0

    rect = pygame.Rect(tn.BIRD_START_X, height // 2, bird_size[0], bird_size[1])
    speed_y = 0.0
    gravity = tn.GRAVITY_PER_FRAME
    flap_impulse = tn.FLAP_IMPULSE

    space_time_0 = -1.0
    space_time_1 = 1.0
    jump_buffer_remaining = 0.0
    next_double_jump_at = 0.0

    points = 0
    scroll_accum = 0.0
    end_flag = False
    shake = 0.0
    death_angle = 0.0

    sysfont_name = pygame.font.get_default_font()
    font_ui = pygame.font.SysFont(sysfont_name, 46)
    font_big = pygame.font.SysFont(sysfont_name, 96)

    running = True
    frame_index = 0
    game_time = 0.0
    saved_results = False

    def bird_hit_rect():
        return pygame.Rect(rect).inflate(-2 * tn.BIRD_HIT_INSET, -2 * tn.BIRD_HIT_INSET)

    def pipe_hit_rect(pr):
        return pygame.Rect(pr).inflate(-2 * tn.PIPE_HIT_INSET, -2 * tn.PIPE_HIT_INSET)

    def attempt_flap():
        nonlocal speed_y, space_time_0, space_time_1
        if rect.top <= 10:
            return False
        if difficulty[-1] == 1:
            now = time.time()
            if space_time_0 == -1:
                space_time_0 = now
                speed_y = flap_impulse
                return True
            space_time_1 = now
            if space_time_1 - space_time_0 > tn.HARD_FLAP_COOLDOWN_SEC:
                speed_y = flap_impulse
                space_time_0 = space_time_1
                return True
            return False
        speed_y = flap_impulse
        return True

    def try_double_jump_rise():
        """Поднять птицу на DOUBLE_JUMP_RISE_PX от текущей позиции (без путаницы со скоростью)."""
        nonlocal rect, next_double_jump_at
        now = time.time()
        if now < next_double_jump_at:
            return False
        if rect.top <= 10:
            return False
        rect.y -= tn.DOUBLE_JUMP_RISE_PX
        rect.y = max(
            tn.BIRD_Y_CLAMP_TOP,
            min(rect.y, height - ground_h - rect.height),
        )
        next_double_jump_at = now + tn.DOUBLE_JUMP_COOLDOWN_SEC
        return True

    def attempt_double_jump_only():
        """Когда обычный взмах не прошёл — фиксированный подъём (не суммировать с взмахом в тот же кадр)."""
        return try_double_jump_rise()

    while running:
        dt = clock.tick(tn.TARGET_FPS) / 1000.0
        dt = min(dt, 0.05)
        game_time += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                if end_flag:
                    return
                jump_buffer_remaining = tn.INPUT_BUFFER_SEC
            elif event.type == pygame.KEYUP and event.key == pygame.K_SPACE:
                if (
                    tn.SHORT_FLAP_ON_KEYUP
                    and not end_flag
                    and speed_y < 0
                ):
                    speed_y *= tn.JUMP_CUT_MULT

        ce_rect = pygame.Rect(0, tn.CEILING_TOP, width, tn.CEILING_HEIGHT)

        if not end_flag:
            if jump_buffer_remaining > 0:
                if attempt_flap():
                    jump_buffer_remaining = 0.0
                elif enable_double_jump and attempt_double_jump_only():
                    jump_buffer_remaining = 0.0
                else:
                    jump_buffer_remaining = max(0.0, jump_buffer_remaining - dt)

        if not end_flag and enable_nitro:
            keys = pygame.key.get_pressed()
            if keys[pygame.K_SPACE] and nitro_fuel > 0:
                nitro_fuel -= tn.NITRO_DRAIN_PER_FRAME
                nitro_fuel = max(0.0, nitro_fuel)
                speed_y += tn.NITRO_LIFT_PER_FRAME

        if not end_flag:
            speed_y += gravity
            rect.y += int(round(speed_y))
            rect.y = max(tn.BIRD_Y_CLAMP_TOP, min(rect.y, height - ground_h - rect.height))

            bh = bird_hit_rect()
            hit_ceiling = bh.colliderect(ce_rect)
            hit_floor = bh.bottom >= height - ground_h

            shield_buff = (
                enable_shield
                and shield_until_gt >= 0
                and game_time < shield_until_gt
            )
            if enable_shield and shield_until_gt >= 0 and game_time >= shield_until_gt:
                shield_until_gt = -1.0

            for i in range(wall_counter):
                list_wall[i].x -= pipe_dx
                list_wall2[i].x -= pipe_dx

                if list_wall[i].right < rect.centerx and not pipe_passed[i]:
                    pipe_passed[i] = True
                    points += 1

                orb = aura_orbs[i]
                ox_c = list_wall[i].centerx
                oy_c = (list_wall2[i].bottom + list_wall[i].top) // 2
                if enable_shield:
                    if (
                        not orb["collected"]
                        and game_time < orb["expire_at"]
                        and list_wall[i].right > -pipe_w
                    ):
                        bird_r = max(bh.width, bh.height) * 0.55
                        dx = bh.centerx - ox_c
                        dy = bh.centery - oy_c
                        if dx * dx + dy * dy <= (tn.AURA_ORB_RADIUS + bird_r) ** 2:
                            orb["collected"] = True
                            shield_until_gt = game_time + tn.AURA_SHIELD_SEC

                if list_wall[i].right < -pipe_w:
                    pipe_passed[i] = False
                    gap_rng_live = gap_hard if difficulty[-1] == 1 else gap_easy
                    mx = max(list_wall[j].right for j in range(wall_counter))
                    mx = max(mx, width)
                    lo, hi = tn.PIPE_RESPAWN_SPACING_EXTRA
                    new_x = mx + spacing + random.randint(lo, hi)
                    full_gap = random.randint(gap_rng_live[0], gap_rng_live[1])
                    gap_half = full_gap // 2
                    vm = tn.PIPE_GAP_VERTICAL_MARGIN
                    cy = random.randint(
                        vm + gap_half,
                        height - ground_h - vm - gap_half,
                    )
                    top_h = cy - gap_half
                    bot_top = cy + gap_half
                    bot_h = height - ground_h - bot_top
                    list_wall2[i] = pygame.Rect(new_x, 0, pipe_w, top_h)
                    list_wall[i] = pygame.Rect(new_x, bot_top, pipe_w, bot_h)
                    aura_orbs[i] = {
                        "expire_at": game_time + tn.AURA_ORB_HANG_SEC,
                        "collected": False,
                    }

                ph_top = pipe_hit_rect(list_wall2[i])
                ph_bot = pipe_hit_rect(list_wall[i])
                pipe_hit = bh.colliderect(ph_top) or bh.colliderect(ph_bot)
                if pipe_hit:
                    invuln_now = invuln_until_gt >= 0 and game_time < invuln_until_gt
                    if invuln_now:
                        pass
                    elif enable_shield and shield_buff:
                        invuln_until_gt = game_time + tn.AURA_PIPE_INVINCIBLE_SEC
                    else:
                        end_flag = True
                        shake = tn.SHAKE_ON_DEATH

            if hit_ceiling or hit_floor:
                end_flag = True
                shake = tn.SHAKE_ON_DEATH

            scroll_accum += scroll_step

        else:
            shake *= tn.SHAKE_DECAY
            death_angle = min(tn.DEATH_TILT_MAX, death_angle + tn.DEATH_TILT_SPEED * dt)
            speed_y += gravity * tn.DEATH_GRAVITY_MULT
            rect.y += int(round(speed_y))
            rect.y = min(rect.y, height - ground_h - rect.height)

        update_clouds(clouds, dt)
        update_wind(wind_parts, dt)

        ox = int(random.uniform(-shake, shake)) if shake > 0.5 else 0
        oy = int(random.uniform(-shake, shake)) if shake > 0.5 else 0

        world = pygame.Surface(size)
        draw_gradient_sky(world, game_time)
        draw_clouds(world, clouds, game_time)
        draw_wind(world, wind_parts, game_time)

        for i in range(wall_counter):
            draw_pipe(world, list_wall2[i], flip=False)
            draw_pipe(world, list_wall[i], flip=True)
            if enable_shield:
                orb = aura_orbs[i]
                if not orb["collected"] and game_time < orb["expire_at"]:
                    ocx = list_wall[i].centerx
                    ocy = (list_wall2[i].bottom + list_wall[i].top) // 2
                    if list_wall[i].right > -tn.AURA_ORB_RADIUS and list_wall[i].left < width + tn.AURA_ORB_RADIUS:
                        draw_gap_aura_orb(world, ocx, ocy, tn.AURA_ORB_RADIUS, game_time + i * 0.7)

        draw_ground(world, scroll_accum, game_time, ground_h)

        frame_index = (frame_index + anim_speed * dt * 60) % (len(Player_Sprite) * 10)
        image = Player_Sprite[int(frame_index / 10)]

        tilt = max(-35, min(55, speed_y * 5))
        if end_flag:
            tilt = death_angle
        bird_draw = pygame.transform.rotozoom(image, -tilt, 1.0)
        br = bird_draw.get_rect(center=rect.center)

        world.blit(bird_draw, br)
        inv_draw = invuln_until_gt >= 0 and game_time < invuln_until_gt
        sh_draw = shield_until_gt >= 0 and game_time < shield_until_gt
        if enable_shield and (inv_draw or sh_draw):
            draw_shield_overlay(world, br, blink_on=inv_draw, t=game_time)

        screen.fill((12, 18, 28))
        screen.blit(world, (ox, oy))

        shadow = pygame.Surface((bird_size[0], 14), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (30, 40, 40, 90), shadow.get_rect())
        screen.blit(
            shadow,
            (rect.centerx - shadow.get_width() // 2 + ox, height - ground_h + 8 + oy),
        )

        outline = pygame.font.SysFont(sysfont_name, 48)
        score_shadow = outline.render(str(points), True, (20, 40, 60))
        score_text = font_ui.render(str(points), True, (255, 245, 230))
        sx, sy = 28 + ox, 36 + oy
        screen.blit(score_shadow, (sx + 3, sy + 3))
        screen.blit(score_text, (sx, sy))

        nf = pygame.font.SysFont(sysfont_name, 20)
        hint_y = sy + 50
        htxt_v = "SPACE — взмах"
        if enable_nitro:
            htxt_v += " / удержание — нитро"
        screen.blit(nf.render(htxt_v, True, (248, 250, 255)), (28 + ox, hint_y))
        hint_y += 22
        if enable_double_jump:
            screen.blit(
                nf.render("При блокировке взмеха доступен двойной подъём (раз в кулдаун)", True, (210, 225, 245)),
                (28 + ox, hint_y),
            )
            hint_y += 22
        if enable_shield:
            screen.blit(
                nf.render(
                    "Сфера в щели → щит: удар по трубе = 1 с неуязвимости",
                    True,
                    (200, 230, 255),
                ),
                (28 + ox, hint_y),
            )
            hint_y += 22
        if enable_nitro:
            nitro_frac = nitro_fuel / max(1e-6, tn.NITRO_MAX_UNITS)
            draw_nitro_bar(screen, 28 + ox, height - 42 + oy, 200, 14, nitro_frac)
            lb = pygame.font.SysFont(sysfont_name, 16).render("НИТРО", True, (180, 200, 220))
            screen.blit(lb, (28 + ox, height - 59 + oy))

        if end_flag:
            if not saved_results:
                saved_results = True
                try:
                    with open(BASE_DIR / "Results.txt", "a", encoding="utf-8") as f:
                        f.write(f"{points} {name[-1]},")
                except OSError:
                    pass

            overlay = pygame.Surface(size, pygame.SRCALPHA)
            overlay.fill((15, 22, 35, 165))
            screen.blit(overlay, (0, 0))
            go = font_big.render("Игра окончена", True, (255, 235, 210))
            scr_line = font_ui.render(f"Счёт: {points}", True, (220, 235, 255))
            gr = go.get_rect(center=(width // 2, height // 2 - 40))
            sr = scr_line.get_rect(center=(width // 2, height // 2 + 10))
            screen.blit(go, gr)
            screen.blit(scr_line, sr)
            hint = pygame.font.SysFont(sysfont_name, 28).render(
                "SPACE — вернуться в меню", True, (200, 220, 255)
            )
            screen.blit(hint, hint.get_rect(center=(width // 2, height // 2 + 70)))

        pygame.display.flip()


# ---------- menu ----------
leaders = read_results()
pygame.init()

screen = pygame.display.set_mode(size)
menu = pygame_menu.Menu("Добро пожаловать", width, height, theme=pygame_menu.themes.THEME_BLUE)
menu.add.text_input("Имя:", default="John Doe", onchange=MyTextValue)
menu.add.selector("Сложность:", [("Сложно", 1), ("Легко", 2)], onchange=set_difficulty)
menu.add.selector(
    "Нитро:",
    [("Вкл.", True), ("Выкл.", False)],
    onchange=set_opt_nitro,
)
menu.add.selector(
    "Щит (аура в щели):",
    [("Вкл.", True), ("Выкл.", False)],
    onchange=set_opt_shield,
)
menu.add.selector(
    "Двойной подъём:",
    [("Вкл.", True), ("Выкл.", False)],
    onchange=set_opt_double_jump,
)
menu.add.button("Играть", start_the_game)
menu.add.button("Выход", pygame_menu.events.EXIT)
menu.add.button("——————————————————")
menu.add.button("Таблица:")
for i in range(6):
    menu.add.button(leaders[i])
menu.mainloop(screen)

pygame.quit()
