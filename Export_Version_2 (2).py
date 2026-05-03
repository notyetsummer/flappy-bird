import math
import random
import time
from pathlib import Path

import pygame
import pygame_menu

# ---------- paths ----------
BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"

size = (1200, 800)
width, height = size
name = ["John Doe"]
difficulty = [1]


def set_difficulty(_, y):
    difficulty.append(y)


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


def draw_gradient_sky(surface, t):
    top = (120 + int(15 * math.sin(t * 0.15)), 185 + int(10 * math.cos(t * 0.12)), 230)
    mid = (170 + int(10 * math.sin(t * 0.2)), 215, 235)
    bot = (235, 245, 255)
    for y in range(height):
        k = y / height
        if k < 0.55:
            u = k / 0.55
            c = (
                int(top[i] + (mid[i] - top[i]) * u) for i in range(3)
            )
        else:
            u = (k - 0.55) / 0.45
            c = (
                int(mid[i] + (bot[i] - mid[i]) * u) for i in range(3)
            )
        pygame.draw.line(surface, tuple(c), (0, y), (width, y))


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


def draw_ground(surface, scroll, t):
    ground_h = 110
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


def spawn_pipe_pair(index, spacing, pipe_w, gap_min, gap_max, ground_h):
    x = width + index * spacing + random.randint(0, 80)
    full_gap = random.randint(gap_min, gap_max)
    gap_half = full_gap // 2
    cy = random.randint(180 + gap_half, height - ground_h - 180 - gap_half)
    top_h = cy - gap_half
    bot_top = cy + gap_half
    bot_h = height - ground_h - bot_top
    top_rect = pygame.Rect(x, 0, pipe_w, top_h)
    bot_rect = pygame.Rect(x, bot_top, pipe_w, bot_h)
    return top_rect, bot_rect


def start_the_game():
    clock = pygame.time.Clock()
    ground_h = 110
    pipe_w = 88
    spacing = 340
    gap_easy = (210, 240)
    gap_hard = (175, 205)
    pipe_speed = 2.8

    gap_rng = gap_hard if difficulty[-1] == 1 else gap_easy
    wall_counter = max(3, int(width / spacing) + 2)

    screen = pygame.display.set_mode(size)
    pygame.display.set_caption("Flappy Bird — улучшенная версия")

    bird_size = (56, 42)
    Player_Sprite = load_bird_frames(bird_size)
    anim_speed = 5

    clouds = init_clouds()
    wind_parts = init_wind_particles()

    list_wall = []
    list_wall2 = []
    pipe_passed = []
    for i in range(wall_counter):
        tr, br = spawn_pipe_pair(i, spacing, pipe_w, gap_rng[0], gap_rng[1], ground_h)
        list_wall2.append(tr)
        list_wall.append(br)
        pipe_passed.append(False)

    rect = pygame.Rect(220, height // 2, bird_size[0], bird_size[1])
    speed_y = 0.0
    gravity = 0.42
    flap_impulse = -8.2

    space_time_0 = -1.0
    space_time_1 = 1.0

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

    while running:
        dt = clock.tick(120) / 1000.0
        dt = min(dt, 0.05)
        game_time += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                if end_flag:
                    return
                if rect.top > 10:
                    if difficulty[-1] == 1:
                        now = time.time()
                        if space_time_0 == -1:
                            space_time_0 = now
                            speed_y = flap_impulse
                        else:
                            space_time_1 = now
                            if space_time_1 - space_time_0 > 1:
                                speed_y = flap_impulse
                                space_time_0 = space_time_1
                    else:
                        speed_y = flap_impulse

        ce_rect = pygame.Rect(0, -40, width, 42)

        if not end_flag:
            speed_y += gravity
            rect.y += int(round(speed_y))
            rect.y = max(-30, min(rect.y, height - ground_h - rect.height))

            hit_ceiling = rect.colliderect(ce_rect)
            hit_floor = rect.bottom >= height - ground_h

            for i in range(wall_counter):
                list_wall[i].x -= int(pipe_speed)
                list_wall2[i].x -= int(pipe_speed)

                if list_wall[i].right < rect.centerx and not pipe_passed[i]:
                    pipe_passed[i] = True
                    points += 1

                if list_wall[i].right < -pipe_w:
                    pipe_passed[i] = False
                    gap_rng_live = gap_hard if difficulty[-1] == 1 else gap_easy
                    mx = max(list_wall[j].right for j in range(wall_counter))
                    mx = max(mx, width)
                    new_x = mx + random.randint(spacing - 40, spacing + 120)
                    full_gap = random.randint(gap_rng_live[0], gap_rng_live[1])
                    gap_half = full_gap // 2
                    cy = random.randint(
                        180 + gap_half,
                        height - ground_h - 180 - gap_half,
                    )
                    top_h = cy - gap_half
                    bot_top = cy + gap_half
                    bot_h = height - ground_h - bot_top
                    list_wall2[i] = pygame.Rect(new_x, 0, pipe_w, top_h)
                    list_wall[i] = pygame.Rect(new_x, bot_top, pipe_w, bot_h)

                if rect.colliderect(list_wall[i]) or rect.colliderect(list_wall2[i]):
                    end_flag = True
                    shake = 14.0

            if hit_ceiling or hit_floor:
                end_flag = True
                shake = 14.0

            scroll_accum += pipe_speed

        else:
            shake *= 0.88
            death_angle = min(75, death_angle + 400 * dt)
            speed_y += gravity * 0.6
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

        draw_ground(world, scroll_accum, game_time)

        frame_index = (frame_index + anim_speed * dt * 60) % (len(Player_Sprite) * 10)
        image = Player_Sprite[int(frame_index / 10)]

        tilt = max(-35, min(55, speed_y * 5))
        if end_flag:
            tilt = death_angle
        bird_draw = pygame.transform.rotozoom(image, -tilt, 1.0)
        br = bird_draw.get_rect(center=rect.center)

        world.blit(bird_draw, br)

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

        small_hint = pygame.font.SysFont(sysfont_name, 22).render(
            "SPACE — взмах", True, (255, 255, 255)
        )
        screen.blit(small_hint, (28 + ox, sy + 52))

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
menu.add.button("Играть", start_the_game)
menu.add.button("Выход", pygame_menu.events.EXIT)
menu.add.button("——————————————————")
menu.add.button("Таблица:")
for i in range(6):
    menu.add.button(leaders[i])
menu.mainloop(screen)

pygame.quit()
