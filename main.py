import random
import math
import json
import os
import sys

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Triangle, Ellipse, Line, Rectangle, Bezier
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.uix.slider import Slider
from kivy.uix.scrollview import ScrollView
from kivy.utils import platform

try:
    from kivy.core.audio import SoundLoader
    AUDIO_AVAILABLE = True
except Exception:
    AUDIO_AVAILABLE = False


IS_MOBILE = platform in ("android", "ios")
IS_DESKTOP = not IS_MOBILE


# ---------- Настройки ----------
SHIP_SIZE = 25
SHIP_SPEED = 360
BULLET_SPEED = 700
BULLET_RADIUS = 4
SHOOT_COOLDOWN = 0.18

ASTEROID_BASE_SPEED = 100
ASTEROID_SPAWN_BASE = 1.4
ASTEROID_SPAWN_MIN = 0.5
ASTEROID_SPEED_PER_SCORE = 2

GAME_NAME = "ASTEROID HUNTER"
UPGRADE_EVERY = 15
MAX_HEARTS = 3

HP_SMALL = 6
HP_LARGE = 12
LARGE_THRESHOLD = 30

LASER_COOLDOWN = 8
LASER_DURATION = 3.0
LASER_EDGE_TICK = 0.25         # тик граней ромба
LASER_EDGE_DAMAGE = 3          # ← 3 урона за тик → 12/сек, большой (12 HP) умирает за 1 сек
BOMB_COOLDOWN = 15

MAX_LEVEL_TRIPLE = 6
MAX_LEVEL_LASER = 4
MAX_LEVEL_BOMB = 4
MAX_LEVEL_SPEED = 4

SPEED_BONUS_PER_LEVEL = 0.10

CRYSTAL_CHANCE = 0.05
CRYSTAL_FALL_SPEED = 90

SETTINGS_FILE = "game_settings.json"

DEFAULT_SETTINGS = {
    "bg_color": [0.01, 0.01, 0.03],
    "sfx_volume": 0.8,
    "music_volume": 0.5,
    "key_up": 119,
    "key_down": 115,
    "key_left": 97,
    "key_right": 100,
    "key_shoot": 32,
}

KEY_NAMES = {
    119: "W", 115: "S", 97: "A", 100: "D", 32: "SPACE",
    273: "UP", 274: "DOWN", 276: "LEFT", 275: "RIGHT",
    113: "Q", 101: "E", 114: "R", 116: "T", 121: "Y", 117: "U",
    105: "I", 111: "O", 112: "P", 102: "F", 103: "G", 104: "H",
    106: "J", 107: "K", 108: "L", 122: "Z", 120: "X", 99: "C",
    118: "V", 98: "B", 110: "N", 109: "M",
}


# ============================================================
#                  НАСТРОЙКИ
# ============================================================

class Settings:
    def __init__(self):
        self.data = dict(DEFAULT_SETTINGS)
        self.load()

    def load(self):
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, "r") as f:
                    loaded = json.load(f)
                    for k, v in loaded.items():
                        if k in self.data:
                            self.data[k] = v
        except Exception:
            pass

    def save(self):
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(self.data, f)
        except Exception:
            pass

    def get(self, key):
        return self.data.get(key, DEFAULT_SETTINGS.get(key))

    def set(self, key, value):
        self.data[key] = value
        self.save()


SETTINGS = Settings()


# ============================================================
#                     ЗВУКИ
# ============================================================

class SoundManager:
    def __init__(self):
        self.sfx_shoot = None
        self.sfx_explosion = None
        self.sfx_hit = None
        self.sfx_pickup = None
        self.music = None
        if AUDIO_AVAILABLE:
            try:
                self.sfx_shoot = SoundLoader.load("shoot.wav")
                self.sfx_explosion = SoundLoader.load("explosion.wav")
                self.sfx_hit = SoundLoader.load("hit.wav")
                self.sfx_pickup = SoundLoader.load("pickup.wav")
                self.music = SoundLoader.load("music.wav")
                if self.music:
                    self.music.loop = True
            except Exception:
                pass

    def play_shoot(self): self._play(self.sfx_shoot)
    def play_explosion(self): self._play(self.sfx_explosion)
    def play_hit(self): self._play(self.sfx_hit)
    def play_pickup(self): self._play(self.sfx_pickup)

    def _play(self, snd):
        if snd is None:
            return
        try:
            snd.volume = SETTINGS.get("sfx_volume")
            snd.play()
        except Exception:
            pass

    def start_music(self):
        if self.music is None:
            return
        try:
            self.music.volume = SETTINGS.get("music_volume")
            if self.music.state != "play":
                self.music.play()
        except Exception:
            pass

    def stop_music(self):
        if self.music is None:
            return
        try:
            self.music.stop()
        except Exception:
            pass

    def update_volumes(self):
        if self.music:
            try:
                self.music.volume = SETTINGS.get("music_volume")
            except Exception:
                pass


SOUND = SoundManager()


# ============================================================
#                 ЗВЁЗДНЫЙ ФОН
# ============================================================

class Starfield:
    def __init__(self, canvas, get_size):
        self.canvas = canvas
        self.get_size = get_size
        self.stars = []
        self.star_gfx = []
        self.tick = 0.0
        self._last_size = (0, 0)
        self.redraw()

    def redraw(self):
        self.canvas.clear()
        w, h = self.get_size()
        self._last_size = (w, h)
        self.stars = []
        self.star_gfx = []
        with self.canvas:
            bg = SETTINGS.get("bg_color")
            Color(bg[0], bg[1], bg[2], 1)
            self.bg_rect = Rectangle(pos=(0, 0), size=(w, h))
            for _ in range(80):
                x = random.uniform(0, w)
                y = random.uniform(0, h)
                brightness = random.uniform(0.4, 1.0)
                size = random.uniform(1.0, 2.4)
                self.stars.append({
                    "x": x, "y": y, "b": brightness, "size": size,
                    "phase": random.uniform(0, math.tau),
                    "speed": random.uniform(0.5, 2.0),
                    "base_speed": random.uniform(5, 25),
                })
                Color(brightness, brightness, brightness, 1)
                e = Ellipse(pos=(x - size, y - size), size=(size * 2, size * 2))
                self.star_gfx.append(e)

    def refresh_bg_color(self):
        self.redraw()

    def update(self, dt):
        w, h = self.get_size()
        if (w, h) != self._last_size:
            self.redraw()
        self.bg_rect.size = (w, h)
        self.tick += dt
        for s, gfx in zip(self.stars, self.star_gfx):
            s["y"] -= s["base_speed"] * dt
            if s["y"] < -5:
                s["y"] = h + 5
                s["x"] = random.uniform(0, w)
            twinkle = 0.6 + 0.4 * math.sin(self.tick * s["speed"] * 2 + s["phase"])
            sz = s["size"] * (0.7 + 0.3 * twinkle)
            gfx.pos = (s["x"] - sz, s["y"] - sz)
            gfx.size = (sz * 2, sz * 2)


# ============================================================
#                     СЕРДЦЕ
# ============================================================

class HeartIcon(Widget):
    def __init__(self, filled=True, size=(28, 28), **kwargs):
        super().__init__(size_hint=(None, None), size=size, **kwargs)
        self.filled = filled
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    def _redraw(self, *args):
        self.canvas.clear()
        w, h = self.size
        x, y = self.pos
        if self.filled:
            color = (0.95, 0.2, 0.3, 1); edge = (1, 0.5, 0.55, 1)
        else:
            color = (0.2, 0.08, 0.1, 1); edge = (0.35, 0.15, 0.18, 1)
        with self.canvas:
            cx = x + w / 2
            top = y + h * 0.9
            bottom = y + h * 0.1
            Color(*color)
            Bezier(points=[cx, bottom, x + w * 0.02, y + h * 0.5, x + w * 0.05, top, cx, top - h * 0.15], segments=20)
            Bezier(points=[x + w * 0.05, top, x + w * 0.35, top - h * 0.1, cx - w * 0.05, y + h * 0.5, cx, bottom], segments=20)
            Bezier(points=[cx, bottom, x + w * 0.98, y + h * 0.5, x + w * 0.95, top, cx, top - h * 0.15], segments=20)
            Bezier(points=[cx, top - h * 0.15, x + w * 0.65, top - h * 0.1, cx + w * 0.05, y + h * 0.5, cx, bottom], segments=20)
            Color(*edge)
            Bezier(points=[cx, bottom, x + w * 0.02, y + h * 0.5, x + w * 0.05, top, cx, top - h * 0.15], segments=20)
            if self.filled:
                Color(1, 0.85, 0.85, 0.7)
                r = w * 0.1
                Ellipse(pos=(x + w * 0.28, y + h * 0.6), size=(r * 2, r))


# ============================================================
#                     ИКОНКИ
# ============================================================

class TripleShotIcon(Widget):
    def __init__(self, size=(90, 90), **kwargs):
        super().__init__(size_hint=(None, None), size=size, **kwargs)
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    def _redraw(self, *args):
        self.canvas.clear()
        w, h = self.size
        x, y = self.pos
        with self.canvas:
            Color(0.1, 0.2, 0.35, 0.6)
            Ellipse(pos=(x + w * 0.05, y + h * 0.05), size=(w * 0.9, h * 0.9))
            for ox in (-w * 0.22, 0, w * 0.22):
                cx = x + w * 0.5 + ox
                Color(0.3, 0.9, 1, 1)
                Triangle(points=[cx, y + h * 0.85,
                                 cx - w * 0.06, y + h * 0.62,
                                 cx + w * 0.06, y + h * 0.62])
                Color(1, 1, 0.4, 1)
                Rectangle(pos=(cx - w * 0.022, y + h * 0.22),
                          size=(w * 0.044, h * 0.4))


class LaserIcon(Widget):
    def __init__(self, size=(90, 90), **kwargs):
        super().__init__(size_hint=(None, None), size=size, **kwargs)
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    def _redraw(self, *args):
        self.canvas.clear()
        w, h = self.size
        x, y = self.pos
        with self.canvas:
            Color(0.25, 0.1, 0.3, 0.6)
            Ellipse(pos=(x + w * 0.05, y + h * 0.05), size=(w * 0.9, h * 0.9))
            cx = x + w * 0.5
            cy = y + h * 0.5
            Color(1, 0.5, 1, 0.8)
            Line(points=[cx, y + h * 0.95, x + w * 0.85, cy,
                         cx, y + h * 0.05, x + w * 0.15, cy,
                         cx, y + h * 0.95], width=2.5)
            Color(1, 1, 1, 1)
            Line(points=[cx, y + h * 0.1, cx, y + h * 0.9], width=3)


class BombIcon(Widget):
    def __init__(self, size=(90, 90), **kwargs):
        super().__init__(size_hint=(None, None), size=size, **kwargs)
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    def _redraw(self, *args):
        self.canvas.clear()
        w, h = self.size
        x, y = self.pos
        with self.canvas:
            Color(0.3, 0.15, 0.05, 0.6)
            Ellipse(pos=(x + w * 0.05, y + h * 0.05), size=(w * 0.9, h * 0.9))
            r = w * 0.26
            cx, cy = x + w * 0.42, y + h * 0.35
            Color(0.12, 0.12, 0.18, 1)
            Ellipse(pos=(cx - r, cy - r), size=(r * 2, r * 2))
            Color(0.6, 0.6, 0.7, 0.7)
            Ellipse(pos=(cx - r * 0.65, cy + r * 0.15),
                    size=(r * 0.55, r * 0.55))
            Color(0.65, 0.45, 0.25, 1)
            Line(points=[cx + r * 0.45, cy + r * 0.75,
                         cx + r * 0.75, cy + r * 1.15,
                         cx + r * 0.55, cy + r * 1.45], width=2.5)
            Color(1, 0.75, 0.2, 1)
            sr = w * 0.08
            Ellipse(pos=(cx + r * 0.55 - sr, cy + r * 1.45 - sr),
                    size=(sr * 2, sr * 2))
            Color(1, 1, 0.6, 1)
            sr2 = w * 0.035
            Ellipse(pos=(cx + r * 0.55 - sr2, cy + r * 1.45 - sr2),
                    size=(sr2 * 2, sr2 * 2))


class SpeedIcon(Widget):
    def __init__(self, size=(90, 90), **kwargs):
        super().__init__(size_hint=(None, None), size=size, **kwargs)
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    def _redraw(self, *args):
        self.canvas.clear()
        w, h = self.size
        x, y = self.pos
        with self.canvas:
            Color(0.1, 0.3, 0.15, 0.6)
            Ellipse(pos=(x + w * 0.05, y + h * 0.05), size=(w * 0.9, h * 0.9))
            for oy in (-h * 0.22, 0, h * 0.22):
                cy = y + h * 0.5 + oy
                Color(0.3, 1, 0.5, 1)
                Rectangle(pos=(x + w * 0.15, cy - h * 0.03),
                          size=(w * 0.55, h * 0.06))
                Color(1, 1, 0.5, 1)
                Triangle(points=[x + w * 0.88, cy,
                                 x + w * 0.68, cy - h * 0.09,
                                 x + w * 0.68, cy + h * 0.09])


class StartButton(Button):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_color = (0, 0, 0, 0)
        self.color = (1, 1, 1, 1)
        self.bind(pos=self._redraw, size=self._redraw, state=self._redraw)

    def _redraw(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            if self.state == "down":
                Color(0.15, 0.5, 0.75, 1)
            else:
                Color(0.2, 0.7, 1, 1)
            Rectangle(pos=self.pos, size=self.size)
            Color(0.3, 0.85, 1, 1)
            Line(rectangle=(self.x + 3, self.y + 3, self.width - 6, self.height - 6), width=2)


class ExitButton(Button):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_color = (0, 0, 0, 0)
        self.color = (1, 1, 1, 1)
        self.bind(pos=self._redraw, size=self._redraw, state=self._redraw)

    def _redraw(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            if self.state == "down":
                Color(0.6, 0.1, 0.1, 1)
            else:
                Color(0.9, 0.2, 0.2, 1)
            Rectangle(pos=self.pos, size=self.size)
            Color(1, 0.5, 0.5, 1)
            Line(rectangle=(self.x + 3, self.y + 3, self.width - 6, self.height - 6), width=2)


# ============================================================
#              СЕНСОРНАЯ КНОПКА
# ============================================================

class TouchButton(Widget):
    def __init__(self, label, key, size=(80, 80), color=(0.2, 0.7, 1, 0.35), **kwargs):
        super().__init__(size_hint=(None, None), size=size, **kwargs)
        self.label = label
        self.key = key
        self.base_color = color
        self.pressed = False
        self.touch_keys_ref = None
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    def _redraw(self, *args):
        self.canvas.clear()
        x, y = self.pos
        w, h = self.size
        with self.canvas:
            c = self.base_color
            alpha = 0.8 if self.pressed else c[3]
            Color(c[0], c[1], c[2], alpha)
            Ellipse(pos=(x, y), size=(w, h))
            Color(1, 1, 1, 1 if self.pressed else 0.7)
            Line(circle=(x + w / 2, y + h / 2, min(w, h) / 2 - 2), width=2)
        if not hasattr(self, "_label_widget"):
            self._label_widget = Label(
                text=self.label, font_size=self.size[0] * 0.5, bold=True,
                color=(1, 1, 1, 1), halign="center", valign="middle",
            )
            self.add_widget(self._label_widget)
        self._label_widget.pos = (x, y)
        self._label_widget.size = self.size

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.pressed = True
            if self.touch_keys_ref is not None:
                self.touch_keys_ref.add(self.key)
            self._redraw()
            return True
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if self.pressed:
            self.pressed = False
            if self.touch_keys_ref is not None:
                self.touch_keys_ref.discard(self.key)
            self._redraw()
            return True
        return super().on_touch_up(touch)


# ============================================================
#                    КРИСТАЛЛ
# ============================================================

class Crystal:
    def __init__(self, canvas, x, y):
        self.x, self.y = x, y
        self.canvas = canvas
        self.radius = 12
        self.timer = 12.0
        self.tick = 0.0
        with canvas:
            Color(0.2, 0.9, 1, 0.35)
            self.glow = Ellipse(pos=(x - 20, y - 20), size=(40, 40))
            Color(0.4, 1, 1, 1)
            self.body = Ellipse(pos=(x - self.radius, y - self.radius),
                                size=(self.radius * 2, self.radius * 2))
            Color(1, 1, 1, 0.9)
            self.shine = Ellipse(pos=(x - 4, y + 2), size=(8, 8))
            self.gfx = [self.glow, self.body, self.shine]

    def update(self, dt):
        self.timer -= dt
        self.tick += dt
        self.y -= CRYSTAL_FALL_SPEED * dt
        pulse = 1.0 + 0.15 * math.sin(self.tick * 4)
        r = self.radius * pulse
        self.body.pos = (self.x - r, self.y - r)
        self.body.size = (r * 2, r * 2)
        self.glow.pos = (self.x - 20 * pulse, self.y - 20 * pulse)
        self.glow.size = (40 * pulse, 40 * pulse)
        self.shine.pos = (self.x - 4, self.y + 2)
        return self.timer > 0 and self.y > -30

    def hits_ship(self, ship):
        dx = ship.x - self.x
        dy = ship.y - self.y
        return (dx * dx + dy * dy) <= (self.radius + SHIP_SIZE * 0.7) ** 2

    def delete(self):
        for g in self.gfx:
            self.canvas.remove(g)
        self.gfx.clear()


# ============================================================
#                     КОРАБЛЬ
# ============================================================

class Ship:
    def __init__(self, canvas, x, y):
        self.x, self.y = x, y
        self.canvas = canvas
        self.hearts = MAX_HEARTS
        self.invuln = 0.0
        self.speed_mult = 1.0
        self.engine_tick = 0.0
        with canvas:
            Color(0.2, 0.9, 1, 1)
            self.tri = Triangle(points=[0, 0, 0, 0, 0, 0])
            Color(0.0, 0.6, 1, 1)
            self.cockpit = Triangle(points=[0, 0, 0, 0, 0, 0])
            Color(1, 0.7, 0.2, 0.9)
            self.engine1 = Ellipse(pos=(0, 0), size=(4, 7))
            Color(1, 0.9, 0.4, 0.9)
            self.engine1_core = Ellipse(pos=(0, 0), size=(2, 4))
            Color(1, 0.7, 0.2, 0.9)
            self.engine2 = Ellipse(pos=(0, 0), size=(4, 7))
            Color(1, 0.9, 0.4, 0.9)
            self.engine2_core = Ellipse(pos=(0, 0), size=(2, 4))
        self.update_graphics()

    def update_graphics(self, dt=0.0):
        self.engine_tick += dt
        x, y, s = self.x, self.y, SHIP_SIZE
        self.tri.points = [x, y + s, x - s * 0.8, y - s * 0.7, x + s * 0.8, y - s * 0.7]
        self.cockpit.points = [x, y + s * 0.4, x - s * 0.35, y - s * 0.2, x + s * 0.35, y - s * 0.2]
        flicker = 0.7 + 0.3 * math.sin(self.engine_tick * 15)
        eh = 7 * flicker
        ex1 = x - s * 0.45
        ey1 = y - s * 0.75
        self.engine1.pos = (ex1 - 2, ey1 - eh / 2)
        self.engine1.size = (4, eh)
        self.engine1_core.pos = (ex1 - 1, ey1 - eh / 4)
        self.engine1_core.size = (2, eh / 2)
        ex2 = x + s * 0.45
        ey2 = y - s * 0.75
        self.engine2.pos = (ex2 - 2, ey2 - eh / 2)
        self.engine2.size = (4, eh)
        self.engine2_core.pos = (ex2 - 1, ey2 - eh / 4)
        self.engine2_core.size = (2, eh / 2)

    def nose(self):
        return (self.x, self.y + SHIP_SIZE)

    def move(self, dx, dy, dt, max_w, max_h):
        speed = SHIP_SPEED * self.speed_mult
        self.x += dx * speed * dt
        self.y += dy * speed * dt
        self.x = max(SHIP_SIZE, min(max_w - SHIP_SIZE, self.x))
        self.y = max(SHIP_SIZE, min(max_h - SHIP_SIZE, self.y))
        self.update_graphics(dt)

    def tick(self, dt):
        self.update_graphics(dt)

    def bounds(self):
        return (self.x - SHIP_SIZE * 0.7, self.y - SHIP_SIZE * 0.6,
                self.x + SHIP_SIZE * 0.7, self.y + SHIP_SIZE)

    def delete(self):
        self.canvas.remove(self.tri)
        self.canvas.remove(self.cockpit)
        self.canvas.remove(self.engine1)
        self.canvas.remove(self.engine1_core)
        self.canvas.remove(self.engine2)
        self.canvas.remove(self.engine2_core)


class Bullet:
    def __init__(self, canvas, x, y, speed_mult=1.0):
        self.x, self.y = x, y
        self.canvas = canvas
        self.speed = BULLET_SPEED * speed_mult
        with canvas:
            Color(1, 1, 0.2, 1)
            self.dot = Ellipse(pos=(x - BULLET_RADIUS, y - BULLET_RADIUS),
                               size=(BULLET_RADIUS * 2, BULLET_RADIUS * 2))

    def update(self, dt):
        self.y += self.speed * dt
        self.dot.pos = (self.x - BULLET_RADIUS, self.y - BULLET_RADIUS)

    def delete(self):
        self.canvas.remove(self.dot)


class ActiveLaser:
    """Лазер от носа корабля.
       - Центральная прямая: УЗКАЯ, убивает сразу (мгновенно).
       - Грани ромба (4 ур.): МОЩНЫЙ постепенный урон — 3 HP каждые 0.25с.
    """
    def __init__(self, canvas, ship, duration, max_h, max_w, diamond=False, wide=False):
        self.canvas = canvas
        self.ship = ship
        self.max_h = max_h
        self.max_w = max_w
        self.timer = duration
        self.diamond = diamond
        self.wide = wide
        # Центральный лазер СТАЛ УЖЕ (было 30 / ×2 = 60)
        base_w = 18
        if wide:
            base_w = int(base_w * 1.6)   # 28 вместо 36
        self.beam_w = base_w
        self.core_w = self.beam_w * 0.4

        self.y_bot = 0
        self.y_top = 0
        self.left_x = 0
        self.right_x = 0
        self.y_mid = 0

        self.shapes = []
        with canvas:
            # Центральная прямая (всегда) — узкая
            Color(1, 0.4, 1, 0.5)
            self.l_core_glow = Line(points=[0, 0, 0, 0], width=self.core_w + 12)
            Color(1, 1, 1, 1)
            self.l_core = Line(points=[0, 0, 0, 0], width=self.core_w)
            self.shapes = [self.l_core_glow, self.l_core]

            # Ромб (4 уровень)
            if diamond:
                Color(1, 0.3, 0.9, 0.45)
                self.l_glow_left = Line(points=[0, 0, 0, 0], width=6)
                self.l_glow_right = Line(points=[0, 0, 0, 0], width=6)
                Color(1, 0.65, 1, 1)
                self.l_left = Line(points=[0, 0, 0, 0], width=4)
                self.l_right = Line(points=[0, 0, 0, 0], width=4)
                self.shapes += [self.l_glow_left, self.l_glow_right,
                                self.l_left, self.l_right]
            else:
                # 1-3 уровень: узкий прямой луч
                Color(1, 0.3, 0.9, 0.35)
                self.glow = Line(points=[0, 0, 0, 0], width=self.beam_w + 10)
                Color(1, 0.5, 1, 0.9)
                self.beam = Line(points=[0, 0, 0, 0], width=self.beam_w)
                self.shapes += [self.glow, self.beam]
        self.update_graphics()

    def update_graphics(self):
        x, ship_nose_y = self.ship.nose()
        y_bot = ship_nose_y + 10
        y_top = self.max_h + 20
        self.y_bot = y_bot
        self.y_top = y_top

        core_pts = [x, y_bot, x, y_top]
        self.l_core_glow.points = core_pts
        self.l_core.points = core_pts

        if self.diamond:
            half_span = self.max_w * 0.35
            y_mid = (y_bot + y_top) / 2
            left_x = max(10, x - half_span)
            right_x = min(self.max_w - 10, x + half_span)
            self.left_x = left_x
            self.right_x = right_x
            self.y_mid = y_mid

            pts_left = [x, y_bot, left_x, y_mid, x, y_top]
            pts_right = [x, y_bot, right_x, y_mid, x, y_top]
            self.l_glow_left.points = pts_left
            self.l_glow_right.points = pts_right
            self.l_left.points = pts_left
            self.l_right.points = pts_right
        else:
            pts = [x, y_bot, x, y_top]
            self.glow.points = pts
            self.beam.points = pts

    def update(self, dt):
        self.timer -= dt
        self.update_graphics()
        return self.timer > 0

    def _dist_to_segment(self, px, py, ax, ay, bx, by):
        dx = bx - ax
        dy = by - ay
        seg_len_sq = dx * dx + dy * dy
        if seg_len_sq < 0.0001:
            return math.hypot(px - ax, py - ay)
        t = ((px - ax) * dx + (py - ay) * dy) / seg_len_sq
        t = max(0.0, min(1.0, t))
        cx = ax + t * dx
        cy = ay + t * dy
        return math.hypot(px - cx, py - cy)

    def in_core(self, ax, ay, ar):
        """Астероид в зоне центральной прямой (узкой)."""
        x = self.ship.x
        if abs(ax - x) <= (self.beam_w * 0.5 + ar):
            if self.y_bot - ar <= ay <= self.y_top + ar:
                return True
        return False

    def in_edge(self, ax, ay, ar):
        """Астероид касается граней ромба (только 4 уровень)."""
        if not self.diamond:
            return False
        x = self.ship.x
        tolerance = 14 + ar
        d1 = self._dist_to_segment(ax, ay, x, self.y_bot, self.left_x, self.y_mid)
        d2 = self._dist_to_segment(ax, ay, self.left_x, self.y_mid, x, self.y_top)
        d3 = self._dist_to_segment(ax, ay, x, self.y_bot, self.right_x, self.y_mid)
        d4 = self._dist_to_segment(ax, ay, self.right_x, self.y_mid, x, self.y_top)
        return min(d1, d2, d3, d4) <= tolerance

    def delete(self):
        for s in self.shapes:
            self.canvas.remove(s)


class Bomb:
    def __init__(self, canvas, x, y, max_h, radius=180, fire_cloud=False):
        self.x, self.y = x, y
        self.canvas = canvas
        self.explode_radius = radius
        self.fire_cloud = fire_cloud
        self.state = "flying"
        self.timer = 0.0
        self.explode_y = max_h * 0.5
        self.body = None
        self.spark = None
        self.collision_radius = 10
        with canvas:
            Color(0.15, 0.15, 0.22, 1)
            self.body = Ellipse(pos=(x - 10, y - 10), size=(20, 20))
            Color(1, 0.7, 0.1, 1)
            self.spark = Ellipse(pos=(x + 4, y + 8), size=(6, 6))

    def update(self, dt, asteroids=None):
        if self.state == "flying":
            self.y += 320 * dt
            if self.body:
                self.body.pos = (self.x - 10, self.y - 10)
            if self.spark:
                self.spark.pos = (self.x + 4, self.y + 8)
            if asteroids:
                for a in asteroids:
                    dx = self.x - a.x
                    dy = self.y - a.y
                    if (dx * dx + dy * dy) <= (a.radius + self.collision_radius) ** 2:
                        self.explode()
                        return
            if self.y >= self.explode_y:
                self.explode()
        elif self.state == "exploding":
            self.timer += dt
            r = self.explode_radius * min(1.0, self.timer / 0.28)
            if self.body:
                self.body.pos = (self.x - r, self.y - r)
                self.body.size = (r * 2, r * 2)
            if self.timer > 0.4:
                self.delete()

    def explode(self):
        self.state = "exploding"
        self.timer = 0.0
        SOUND.play_explosion()
        if self.body:
            self.canvas.remove(self.body)
        if self.spark:
            self.canvas.remove(self.spark)
            self.spark = None
        color = (1, 0.35, 0.05, 0.7) if self.fire_cloud else (1, 0.6, 0.2, 0.6)
        with self.canvas:
            Color(*color)
            self.body = Ellipse(pos=(self.x, self.y), size=(0, 0))

    def hits(self, ax, ay, ar):
        if self.state != "exploding" or self.timer > 0.28:
            return False
        r = self.explode_radius * min(1.0, self.timer / 0.28)
        dx, dy = ax - self.x, ay - self.y
        return (dx * dx + dy * dy) <= (r + ar) ** 2

    def delete(self):
        if self.body:
            self.canvas.remove(self.body)
            self.body = None
        if self.spark:
            self.canvas.remove(self.spark)
            self.spark = None
        self.state = "done"


class FireCloud:
    def __init__(self, canvas, x, y, radius, duration=2.5):
        self.x, self.y = x, y
        self.canvas = canvas
        self.radius = radius
        self.timer = duration
        self.duration = duration
        self.tick = 0.0
        self.particles = []
        self.particle_gfx = []
        for _ in range(20):
            angle = random.uniform(0, math.tau)
            dist = random.uniform(0, radius * 0.85)
            self.particles.append({
                "x": x + math.cos(angle) * dist,
                "y": y + math.sin(angle) * dist,
                "size": random.uniform(6, 14),
                "phase": random.uniform(0, math.tau),
                "speed": random.uniform(1, 3),
            })
        with canvas:
            for p in self.particles:
                Color(1, 0.4, 0.1, 0.7)
                e = Ellipse(pos=(p["x"] - p["size"], p["y"] - p["size"]),
                            size=(p["size"] * 2, p["size"] * 2))
                self.particle_gfx.append(e)

    def update(self, dt):
        self.timer -= dt
        self.tick += dt
        if self.timer <= 0:
            return False
        for p, gfx in zip(self.particles, self.particle_gfx):
            sz = p["size"] * (0.85 + 0.25 * math.sin(self.tick * p["speed"] + p["phase"]))
            gfx.pos = (p["x"] - sz, p["y"] - sz)
            gfx.size = (sz * 2, sz * 2)
        return True

    def hits(self, ax, ay, ar):
        if self.timer <= 0:
            return False
        dx, dy = ax - self.x, ay - self.y
        return (dx * dx + dy * dy) <= (self.radius + ar) ** 2

    def delete(self):
        for gfx in self.particle_gfx:
            self.canvas.remove(gfx)
        self.particle_gfx.clear()


class Explosion:
    def __init__(self, canvas, x, y, max_radius, color=(1, 0.6, 0.2)):
        self.x, self.y = x, y
        self.canvas = canvas
        self.timer = 0.0
        self.duration = 0.45
        self.max_radius = max_radius
        self.particles = []
        num = 10 + int(max_radius / 4)
        for _ in range(num):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(60, 220)
            size = random.uniform(2.5, 6.0)
            self.particles.append({
                "x": x, "y": y,
                "vx": math.cos(angle) * speed,
                "vy": math.sin(angle) * speed,
                "size": size,
                "color": (color[0] * random.uniform(0.8, 1.0),
                          color[1] * random.uniform(0.7, 1.0),
                          color[2] * random.uniform(0.5, 1.0)),
            })
        self.flash = None
        self.particle_gfx = []
        with canvas:
            Color(1, 1, 0.85, 1)
            self.flash = Ellipse(pos=(x, y), size=(0, 0))
            for p in self.particles:
                Color(p["color"][0], p["color"][1], p["color"][2], 1)
                self.particle_gfx.append(Ellipse(pos=(x, y),
                                                  size=(p["size"] * 2, p["size"] * 2)))

    def update(self, dt):
        if self.timer >= self.duration:
            return False
        self.timer += dt
        t = self.timer / self.duration
        flash_r = self.max_radius * min(1.0, t / 0.4)
        self.flash.pos = (self.x - flash_r, self.y - flash_r)
        self.flash.size = (flash_r * 2, flash_r * 2)
        for p, gfx in zip(self.particles, self.particle_gfx):
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["vx"] *= (1 - 2.5 * dt)
            p["vy"] *= (1 - 2.5 * dt)
            gfx.pos = (p["x"] - p["size"], p["y"] - p["size"])
        return True

    def delete(self):
        if self.flash:
            self.canvas.remove(self.flash)
            self.flash = None
        for gfx in self.particle_gfx:
            self.canvas.remove(gfx)
        self.particle_gfx.clear()


class Asteroid:
    def __init__(self, canvas, x, y, speed, radius):
        self.x, self.y = x, y
        self.speed = speed
        self.radius = radius
        self.canvas = canvas
        self.max_hp = HP_LARGE if radius >= LARGE_THRESHOLD else HP_SMALL
        self.hp = self.max_hp
        self.laser_edge_tick = 0.0
        with canvas:
            Color(0.55, 0.48, 0.4, 1)
            self.body = Ellipse(pos=(x - radius, y - radius), size=(radius * 2, radius * 2))
            Color(0.35, 0.3, 0.25, 1)
            self.crater1 = Ellipse(pos=(x, y), size=(0, 0))
            Color(0.4, 0.34, 0.28, 1)
            self.crater2 = Ellipse(pos=(x, y), size=(0, 0))
            Color(0.3, 0.26, 0.22, 1)
            self.crater3 = Ellipse(pos=(x, y), size=(0, 0))
            Color(0.2, 0.2, 0.2, 1)
            self.hp_bg = Rectangle(pos=(0, 0), size=(0, 0))
            Color(0.3, 0.9, 0.3, 1)
            self.hp_fg = Rectangle(pos=(0, 0), size=(0, 0))
        self.update_graphics()

    def update_graphics(self):
        r = self.radius
        self.body.pos = (self.x - r, self.y - r)
        self.body.size = (r * 2, r * 2)
        self.crater1.pos = (self.x - r * 0.55, self.y - r * 0.45)
        self.crater1.size = (r * 0.55, r * 0.55)
        self.crater2.pos = (self.x + r * 0.05, self.y)
        self.crater2.size = (r * 0.4, r * 0.4)
        self.crater3.pos = (self.x - r * 0.25, self.y + r * 0.4)
        self.crater3.size = (r * 0.28, r * 0.28)
        bw = r * 2
        bh = 4
        bx = self.x - r
        by = self.y + r + 6
        self.hp_bg.pos = (bx, by)
        self.hp_bg.size = (bw, bh)
        ratio = max(0.0, self.hp / self.max_hp)
        self.hp_fg.pos = (bx, by)
        self.hp_fg.size = (bw * ratio, bh)

    def update(self, dt):
        self.y -= self.speed * dt
        self.update_graphics()

    def hit(self, px, py):
        dx, dy = px - self.x, py - self.y
        return (dx * dx + dy * dy) <= (self.radius + BULLET_RADIUS) ** 2

    def take_damage(self, dmg):
        self.hp -= dmg
        return self.hp <= 0

    def hits_ship(self, ship):
        x1, y1, x2, y2 = ship.bounds()
        cx = max(x1, min(self.x, x2))
        cy = max(y1, min(self.y, y2))
        dx, dy = self.x - cx, self.y - cy
        return (dx * dx + dy * dy) <= self.radius ** 2

    def delete(self):
        self.canvas.remove(self.body)
        self.canvas.remove(self.crater1)
        self.canvas.remove(self.crater2)
        self.canvas.remove(self.crater3)
        self.canvas.remove(self.hp_bg)
        self.canvas.remove(self.hp_fg)


# ============================================================
#                 ДАННЫЕ СПОСОБНОСТЕЙ
# ============================================================

ABILITIES = {
    "triple": {
        "name": "ТРОЙНОЙ ВЫСТРЕЛ",
        "max": MAX_LEVEL_TRIPLE,
        "desc": [
            "Стреляет 3 пулями вместо 2",
            "+25% к урону пуль",
            "Скорострельность +50%",
            "Шанс крит-урона 15%",
            "Снаряды летят в 1.5 раза быстрее",
            "Каждый 25-й выстрел — дуга из 8 рядов",
        ],
    },
    "laser": {
        "name": "ЛАЗЕР",
        "max": MAX_LEVEL_LASER,
        "desc": [
            "Узкий луч (мгновенно убивает)",
            "+2 сек к продолжительности",
            "Луч шире",
            "Ромбовидные грани (мощный постепенный урон)",
        ],
    },
    "bomb": {
        "name": "БОМБА",
        "max": MAX_LEVEL_BOMB,
        "desc": [
            "Взрыв по площади каждые 15 сек",
            "Перезарядка -3 сек",
            "Снаряды летят в 1.5 раза быстрее",
            "Увеличенный радиус + огненное облако",
        ],
    },
    "speed": {
        "name": "СКОРОСТЬ",
        "max": MAX_LEVEL_SPEED,
        "desc": [
            "+10% к скорости корабля",
            "Ещё +10% к скорости",
            "Ещё +10% к скорости",
            "Ещё +10% к скорости (макс. +40%)",
        ],
    },
}


# ============================================================
#                        ЭКРАНЫ
# ============================================================

class MainMenu(FloatLayout):
    def __init__(self, on_start, on_settings, on_exit, **kwargs):
        super().__init__(**kwargs)

        self.starfield = Starfield(self.canvas.before, lambda: (Window.width, Window.height))
        self._ev = Clock.schedule_interval(self._update, 1 / 60)

        ship_widget = Widget(size_hint=(None, None), size=(120, 120),
                              pos_hint={"center_x": 0.5, "center_y": 0.85})
        with ship_widget.canvas:
            Color(0.2, 0.9, 1, 1)
            Triangle(points=[60, 110, 10, 20, 110, 20])
            Color(0.0, 0.6, 1, 1)
            Triangle(points=[60, 80, 35, 40, 85, 40])
            Color(1, 0.7, 0.2, 0.9)
            Ellipse(pos=(42, 10), size=(5, 10))
            Ellipse(pos=(73, 10), size=(5, 10))
        self.add_widget(ship_widget)

        title = Label(text=GAME_NAME, font_size=54, bold=True,
                      halign="center", valign="middle",
                      size_hint=(1, None), height=100,
                      pos_hint={"center_x": 0.5, "center_y": 0.68},
                      color=(0.2, 0.9, 1, 1))
        self.add_widget(title)

        subtitle = Label(text="Уничтожай астероиды, собирай кристаллы, прокачивайся!",
                         font_size=20, halign="center",
                         size_hint=(1, None), height=40,
                         pos_hint={"center_x": 0.5, "center_y": 0.56},
                         color=(0.8, 0.8, 0.9, 1))
        self.add_widget(subtitle)

        start_btn = StartButton(text="НАЧАТЬ", font_size=28, bold=True,
                                size_hint=(None, None), size=(280, 70),
                                pos_hint={"center_x": 0.5, "center_y": 0.42})
        start_btn.bind(on_release=lambda *_: on_start())
        self.add_widget(start_btn)

        settings_btn = StartButton(text="НАСТРОЙКИ", font_size=24, bold=True,
                                   size_hint=(None, None), size=(280, 60),
                                   pos_hint={"center_x": 0.5, "center_y": 0.31})
        settings_btn.bind(on_release=lambda *_: on_settings())
        self.add_widget(settings_btn)

        exit_btn = ExitButton(text="ВЫХОД", font_size=24, bold=True,
                              size_hint=(None, None), size=(280, 60),
                              pos_hint={"center_x": 0.5, "center_y": 0.21})
        exit_btn.bind(on_release=lambda *_: on_exit())
        self.add_widget(exit_btn)

        ctrl_text = "Экранные кнопки — движение и стрельба" if IS_MOBILE else \
                    "WASD — движение  |  Пробел — стрельба  |  ESC — пауза  |  F11 — полный экран"
        controls = Label(text=ctrl_text, font_size=14, halign="center",
                         size_hint=(1, None), height=30,
                         pos_hint={"center_x": 0.5, "y": 0.03},
                         color=(0.6, 0.6, 0.7, 1))
        self.add_widget(controls)

    def _update(self, dt):
        self.starfield.update(dt)


class GameScreen(FloatLayout):
    def __init__(self, on_game_over, on_upgrade, **kwargs):
        super().__init__(**kwargs)
        self.on_game_over = on_game_over
        self.on_upgrade = on_upgrade

        self.starfield = Starfield(self.canvas.before, lambda: (Window.width, Window.height))

        self.ship = None
        self.bullets = []
        self.asteroids = []
        self.bombs = []
        self.fire_clouds = []
        self.active_lasers = []
        self.explosions = []
        self.crystals = []
        self.score = 0
        self.shoot_timer = 0
        self.spawn_timer = 0
        self.spawn_interval = ASTEROID_SPAWN_BASE

        self.levels = {"triple": 0, "laser": 0, "bomb": 0, "speed": 0}
        self.speed_unlocked = False
        self.laser_cd = 0
        self.bomb_cd = 0
        self.next_upgrade_score = UPGRADE_EVERY
        self.shot_counter = 0
        self.crit_chance = 0.0

        self.touch_keys = set()
        self.touch_buttons = []

        self._ui_box = BoxLayout(orientation="vertical",
                                  size_hint=(None, None), size=(400, 130),
                                  pos_hint={"x": 0.01, "top": 0.99})
        self.score_label = Label(text="SCORE: 0", font_size=22,
                                  halign="left", valign="middle", color=(1, 1, 1, 1))
        self.score_label.bind(size=lambda *_: setattr(self.score_label, "text_size", self.score_label.size))

        self.hearts_box = BoxLayout(orientation="horizontal", spacing=4,
                                     size_hint=(None, None), size=(100, 30))
        self.heart_icons = []
        for _ in range(MAX_HEARTS):
            h = HeartIcon(filled=True, size=(28, 28))
            self.heart_icons.append(h)
            self.hearts_box.add_widget(h)

        self.abilities_label = Label(text="", font_size=13,
                                      halign="left", valign="middle", color=(0.7, 0.9, 1, 1))
        self.abilities_label.bind(size=lambda *_: setattr(self.abilities_label, "text_size", self.abilities_label.size))

        self._ui_box.add_widget(self.score_label)
        self._ui_box.add_widget(self.hearts_box)
        self._ui_box.add_widget(self.abilities_label)
        self.add_widget(self._ui_box)

        self.start()
        if IS_MOBILE:
            self.build_touch_controls()

    def build_touch_controls(self):
        self.clear_touch_controls()
        w, h = Window.width, Window.height
        bs = int(min(w, h) * 0.13)
        m = int(min(w, h) * 0.03)

        btn_up = TouchButton("▲", SETTINGS.get("key_up"), size=(bs, bs),
                              pos=(m + bs, m + bs * 2))
        btn_down = TouchButton("▼", SETTINGS.get("key_down"), size=(bs, bs),
                                pos=(m + bs, m))
        btn_left = TouchButton("◀", SETTINGS.get("key_left"), size=(bs, bs),
                                pos=(m, m + bs))
        btn_right = TouchButton("▶", SETTINGS.get("key_right"), size=(bs, bs),
                                 pos=(m + bs * 2, m + bs))
        fire_btn = TouchButton("FIRE", SETTINGS.get("key_shoot"),
                                size=(int(bs * 1.4), int(bs * 1.4)),
                                color=(1, 0.4, 0.2, 0.4),
                                pos=(w - m - int(bs * 1.4), m))

        for b in (btn_up, btn_down, btn_left, btn_right, fire_btn):
            b.touch_keys_ref = self.touch_keys
            self.touch_buttons.append(b)
            self.add_widget(b)

    def clear_touch_controls(self):
        self.touch_keys.clear()
        for b in self.touch_buttons:
            b.touch_keys_ref = None
            try:
                self.remove_widget(b)
            except Exception:
                pass
        self.touch_buttons.clear()

    def on_size(self, *args):
        if IS_MOBILE and self.touch_buttons:
            self.build_touch_controls()
        self._ui_box.pos_hint = {"x": 0.01, "top": 0.99}
        if self.ship:
            self.ship.x = max(SHIP_SIZE, min(Window.width - SHIP_SIZE, self.ship.x))
            self.ship.y = max(SHIP_SIZE, min(Window.height - SHIP_SIZE, self.ship.y))
            self.ship.update_graphics()

    def start(self):
        w, h = Window.width, Window.height
        self.ship = Ship(self.canvas, w / 2, 100)
        self.bullets = []
        self.asteroids = []
        self.bombs = []
        self.fire_clouds = []
        self.active_lasers = []
        self.explosions = []
        self.crystals = []
        self.score = 0
        self.shoot_timer = 0
        self.spawn_timer = 0
        self.spawn_interval = ASTEROID_SPAWN_BASE
        self.next_upgrade_score = UPGRADE_EVERY
        self.levels = {"triple": 0, "laser": 0, "bomb": 0, "speed": 0}
        self.speed_unlocked = False
        self.laser_cd = 0
        self.bomb_cd = 0
        self.shot_counter = 0
        self.crit_chance = 0.0
        self.update_ui()

    def update_ui(self):
        self.score_label.text = f"SCORE: {self.score}"
        for i, h in enumerate(self.heart_icons):
            h.filled = i < self.ship.hearts
            h._redraw()
        parts = []
        if self.levels["triple"] > 0:
            parts.append(f"TRIPLE Lv{self.levels['triple']}")
        if self.levels["laser"] > 0:
            parts.append(f"LASER Lv{self.levels['laser']} ({int(self.laser_cd)}s)")
        if self.levels["bomb"] > 0:
            parts.append(f"BOMB Lv{self.levels['bomb']} ({int(self.bomb_cd)}s)")
        if self.levels["speed"] > 0:
            parts.append(f"SPEED Lv{self.levels['speed']} (+{self.levels['speed']*10}%)")
        self.abilities_label.text = " | ".join(parts)

    def spawn_explosion(self, x, y, radius):
        color = (1, 0.4, 0.1) if radius >= LARGE_THRESHOLD else (1, 0.7, 0.3)
        self.explosions.append(Explosion(self.canvas, x, y,
                                          max_radius=radius * 1.6, color=color))
        SOUND.play_explosion()

    def update(self, dt, keys):
        if not self.ship:
            return

        all_keys = self.touch_keys | keys
        w, h = Window.width, Window.height
        self.starfield.update(dt)
        self.ship.tick(dt)

        dx = dy = 0
        if SETTINGS.get("key_up") in all_keys: dy += 1
        if SETTINGS.get("key_down") in all_keys: dy -= 1
        if SETTINGS.get("key_left") in all_keys: dx -= 1
        if SETTINGS.get("key_right") in all_keys: dx += 1
        if 273 in all_keys: dy += 1
        if 274 in all_keys: dy -= 1
        if 276 in all_keys: dx -= 1
        if 275 in all_keys: dx += 1

        if dx or dy:
            n = (dx * dx + dy * dy) ** 0.5
            self.ship.move(dx / n, dy / n, dt, w, h)

        self.shoot_timer -= dt
        if SETTINGS.get("key_shoot") in all_keys and self.shoot_timer <= 0:
            cooldown = SHOOT_COOLDOWN
            if self.levels["triple"] >= 3:
                cooldown *= 0.5
            self.shoot_timer = cooldown
            self.fire()

        if self.levels["laser"] > 0:
            self.laser_cd -= dt
            if self.laser_cd <= 0:
                cd = LASER_COOLDOWN
                if self.levels["laser"] >= 3:
                    cd += 3
                self.laser_cd = cd
                self.fire_laser()

        if self.levels["bomb"] > 0:
            self.bomb_cd -= dt
            if self.bomb_cd <= 0:
                cd = BOMB_COOLDOWN
                if self.levels["bomb"] >= 2:
                    cd -= 3
                self.bomb_cd = cd
                self.fire_bomb()

        for b in list(self.bullets):
            b.update(dt)
            if b.y > h + 20:
                b.delete()
                self.bullets.remove(b)

        # Лазер: центр — мгновенно; грани — мощный постепенный урон (3 / 0.25с)
        for lz in list(self.active_lasers):
            if not lz.update(dt):
                lz.delete()
                self.active_lasers.remove(lz)
                continue
            for a in list(self.asteroids):
                # 1) Центр — мгновенно
                if lz.in_core(a.x, a.y, a.radius):
                    self.spawn_explosion(a.x, a.y, a.radius)
                    self.maybe_drop_crystal(a.x, a.y)
                    a.delete()
                    if a in self.asteroids:
                        self.asteroids.remove(a)
                    self.score += 1
                    self.check_upgrade()
                    continue

                # 2) Грани — постепенно (3 HP каждые 0.25с)
                if lz.in_edge(a.x, a.y, a.radius):
                    a.laser_edge_tick += dt
                    if a.laser_edge_tick >= LASER_EDGE_TICK:
                        a.laser_edge_tick -= LASER_EDGE_TICK
                        killed = a.take_damage(LASER_EDGE_DAMAGE)
                        a.update_graphics()
                        SOUND.play_hit()
                        if killed:
                            self.spawn_explosion(a.x, a.y, a.radius)
                            self.maybe_drop_crystal(a.x, a.y)
                            a.delete()
                            self.asteroids.remove(a)
                            self.score += 1
                            self.check_upgrade()
                else:
                    a.laser_edge_tick = 0.0

        for bomb in list(self.bombs):
            bomb.update(dt, asteroids=self.asteroids)
            if bomb.state == "exploding":
                for a in list(self.asteroids):
                    if bomb.hits(a.x, a.y, a.radius):
                        self.spawn_explosion(a.x, a.y, a.radius)
                        self.maybe_drop_crystal(a.x, a.y)
                        a.delete()
                        self.asteroids.remove(a)
                        self.score += 1
            if bomb.state == "done":
                if self.levels["bomb"] >= 4 and bomb.fire_cloud:
                    self.fire_clouds.append(FireCloud(self.canvas, bomb.x, bomb.y,
                                                       radius=bomb.explode_radius, duration=2.5))
                self.bombs.remove(bomb)

        for fc in list(self.fire_clouds):
            if not fc.update(dt):
                fc.delete()
                self.fire_clouds.remove(fc)
                continue
            for a in list(self.asteroids):
                if fc.hits(a.x, a.y, a.radius):
                    killed = a.take_damage(1)
                    a.update_graphics()
                    if killed:
                        self.spawn_explosion(a.x, a.y, a.radius)
                        self.maybe_drop_crystal(a.x, a.y)
                        a.delete()
                        self.asteroids.remove(a)
                        self.score += 1
                        self.check_upgrade()

        for c in list(self.crystals):
            if not c.update(dt):
                c.delete()
                self.crystals.remove(c)
                continue
            if c.hits_ship(self.ship):
                if self.ship.hearts < MAX_HEARTS:
                    self.ship.hearts += 1
                    SOUND.play_pickup()
                c.delete()
                self.crystals.remove(c)

        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            self.spawn_timer = self.spawn_interval
            self.spawn_asteroid(w)

        for a in list(self.asteroids):
            a.update(dt)

            hit_bullet = None
            for b in self.bullets:
                if a.hit(b.x, b.y):
                    hit_bullet = b
                    break
            if hit_bullet:
                dmg = 1
                if self.levels["triple"] >= 2 and random.random() < 0.25:
                    dmg += 1
                if self.crit_chance > 0 and random.random() < self.crit_chance:
                    dmg *= 2
                hit_bullet.delete()
                self.bullets.remove(hit_bullet)
                killed = a.take_damage(dmg)
                a.update_graphics()
                SOUND.play_hit()
                if killed:
                    self.spawn_explosion(a.x, a.y, a.radius)
                    self.maybe_drop_crystal(a.x, a.y)
                    a.delete()
                    self.asteroids.remove(a)
                    self.score += 1
                    self.check_upgrade()
                continue

            if a.y < -a.radius * 2:
                a.delete()
                self.asteroids.remove(a)
                continue

            if a.hits_ship(self.ship) and self.ship.invuln <= 0:
                self.spawn_explosion(a.x, a.y, a.radius)
                a.delete()
                self.asteroids.remove(a)
                self.ship.hearts -= 1
                self.ship.invuln = 1.5
                self.update_ui()
                if self.ship.hearts <= 0:
                    self.destroy_all()
                    self.on_game_over(self.score)
                    return

        if self.ship.invuln > 0:
            self.ship.invuln -= dt

        for ex in list(self.explosions):
            if not ex.update(dt):
                ex.delete()
                self.explosions.remove(ex)

        self.update_ui()

    def maybe_drop_crystal(self, x, y):
        if random.random() < CRYSTAL_CHANCE:
            self.crystals.append(Crystal(self.canvas, x, y))

    def fire(self):
        x, y = self.ship.x, self.ship.y + SHIP_SIZE
        speed_mult = 1.5 if self.levels["triple"] >= 5 else 1.0
        self.shot_counter += 1

        if self.levels["triple"] >= 6 and self.shot_counter % 25 == 0:
            for row in range(8):
                offset_y = y + row * 10
                for col in range(9):
                    spread = (col - 4) * 24
                    extra = row * (col - 4) * 5
                    bx = x + spread + extra
                    self.bullets.append(Bullet(self.canvas, bx, offset_y, speed_mult))
            SOUND.play_shoot()
            return

        if self.levels["triple"] > 0:
            self.bullets.append(Bullet(self.canvas, x, y, speed_mult))
            self.bullets.append(Bullet(self.canvas, x - 15, y, speed_mult))
            self.bullets.append(Bullet(self.canvas, x + 15, y, speed_mult))
        else:
            offset = SHIP_SIZE * 0.6
            self.bullets.append(Bullet(self.canvas, x - offset, y, speed_mult))
            self.bullets.append(Bullet(self.canvas, x + offset, y, speed_mult))
        SOUND.play_shoot()

    def fire_laser(self):
        duration = LASER_DURATION
        if self.levels["laser"] >= 2:
            duration += 2
        diamond = self.levels["laser"] >= 4
        wide = self.levels["laser"] >= 3
        self.active_lasers.append(ActiveLaser(self.canvas, self.ship, duration,
                                              Window.height, Window.width,
                                              diamond, wide))

    def fire_bomb(self):
        radius = 240 if self.levels["bomb"] >= 4 else 180
        fire_cloud = self.levels["bomb"] >= 4
        bomb = Bomb(self.canvas, self.ship.x, self.ship.y, Window.height,
                    radius=radius, fire_cloud=fire_cloud)
        self.bombs.append(bomb)

    def check_upgrade(self):
        while self.score >= self.next_upgrade_score:
            self.next_upgrade_score += UPGRADE_EVERY
            self.on_upgrade()

    def update_difficulty(self):
        self.spawn_interval = max(
            ASTEROID_SPAWN_MIN,
            ASTEROID_SPAWN_BASE - self.score * 0.02,
        )

    def spawn_asteroid(self, w):
        radius = random.choice([
            random.randint(14, 25),
            random.randint(15, 25),
            random.randint(30, 45),
        ])
        x = random.randint(int(radius), int(w - radius))
        y = Window.height + radius
        speed = ASTEROID_BASE_SPEED + self.score * ASTEROID_SPEED_PER_SCORE + random.randint(0, 30)
        self.asteroids.append(Asteroid(self.canvas, x, y, speed, radius))
        self.update_difficulty()

    def available_abilities(self):
        result = []
        for k in ("triple", "laser", "bomb"):
            if self.levels[k] < ABILITIES[k]["max"]:
                result.append(k)
        if self.speed_unlocked:
            if self.levels["speed"] < MAX_LEVEL_SPEED:
                result.append("speed")
        return result

    def check_speed_unlock(self):
        if self.speed_unlocked:
            return
        for k in ("triple", "laser", "bomb"):
            if self.levels[k] >= ABILITIES[k]["max"]:
                self.speed_unlocked = True
                return

    def apply_upgrade(self, key):
        max_lvl = ABILITIES[key]["max"]
        self.levels[key] = min(max_lvl, self.levels[key] + 1)
        lvl = self.levels[key]
        if key == "triple" and lvl == 4:
            self.crit_chance = 0.15
        if key == "laser":
            self.laser_cd = 0
        elif key == "bomb":
            self.bomb_cd = 0
        elif key == "speed":
            self.ship.speed_mult = 1.0 + SPEED_BONUS_PER_LEVEL * lvl
        self.check_speed_unlock()
        self.update_ui()

    def destroy_all(self):
        if self.ship:
            self.ship.delete()
            self.ship = None
        for b in self.bullets: b.delete()
        for a in self.asteroids: a.delete()
        for bomb in self.bombs: bomb.delete()
        for fc in self.fire_clouds: fc.delete()
        for lz in self.active_lasers: lz.delete()
        for ex in self.explosions: ex.delete()
        for c in self.crystals: c.delete()
        self.bullets.clear()
        self.asteroids.clear()
        self.bombs.clear()
        self.fire_clouds.clear()
        self.active_lasers.clear()
        self.explosions.clear()
        self.crystals.clear()
        self.clear_touch_controls()


class UpgradePopup(FloatLayout):
    def __init__(self, on_choose, levels, available, **kwargs):
        super().__init__(**kwargs)

        with self.canvas.before:
            Color(0, 0, 0, 0.85)
            Rectangle(pos=(0, 0), size=(Window.width, Window.height))

        title = Label(text="ВЫБЕРИ УЛУЧШЕНИЕ", font_size=36, bold=True,
                      halign="center", valign="middle",
                      size_hint=(1, None), height=60,
                      pos_hint={"center_x": 0.5, "top": 0.95},
                      color=(1, 1, 0.4, 1))
        self.add_widget(title)

        n = len(available)
        cols = min(4, n)
        grid = GridLayout(cols=cols, spacing=20, padding=30,
                          size_hint=(None, None), size=(min(1100, 240 * cols + 60), 480),
                          pos_hint={"center_x": 0.5, "center_y": 0.42})
        self.add_widget(grid)

        icon_factory = {
            "triple": lambda: TripleShotIcon(size=(90, 90)),
            "laser": lambda: LaserIcon(size=(90, 90)),
            "bomb": lambda: BombIcon(size=(90, 90)),
            "speed": lambda: SpeedIcon(size=(90, 90)),
        }

        def make_card(key):
            lvl = levels[key]
            info = ABILITIES[key]
            max_lvl = info["max"]
            card = BoxLayout(orientation="vertical", spacing=6, padding=12)
            icon = icon_factory[key]()
            icon.bind(on_touch_down=lambda w, t, k=key: self._click(w, t, k, on_choose))
            card.add_widget(icon)
            lvl_text = "MAXX" if lvl >= max_lvl else f"Lv{lvl} → Lv{lvl + 1}"
            lbl = Label(text=f"{info['name']}\n{lvl_text}",
                        font_size=20, bold=True, halign="center", color=(1, 1, 1, 1))
            lbl.bind(size=lambda *_: setattr(lbl, "text_size", lbl.size))
            card.add_widget(lbl)
            if lvl >= max_lvl:
                d = Label(text="Максимальный уровень", font_size=15,
                          halign="center", valign="middle", color=(0.5, 0.9, 0.5, 1))
            else:
                d = Label(text=info["desc"][lvl], font_size=15,
                          halign="center", valign="middle", color=(0.85, 0.9, 1, 1))
            d.bind(size=lambda *_: setattr(d, "text_size", d.size))
            card.add_widget(d)
            return card

        for key in available:
            grid.add_widget(make_card(key))

    def _click(self, widget, touch, key, on_choose):
        if widget.collide_point(*touch.pos):
            on_choose(key)
            return True
        return False


class PauseOverlay(FloatLayout):
    def __init__(self, on_resume, on_menu, **kwargs):
        super().__init__(**kwargs)

        with self.canvas.before:
            Color(0, 0, 0, 0.75)
            Rectangle(pos=(0, 0), size=(Window.width, Window.height))

        title = Label(text="ПАУЗА", font_size=56, bold=True,
                      halign="center", valign="middle",
                      size_hint=(1, None), height=80,
                      pos_hint={"center_x": 0.5, "center_y": 0.7},
                      color=(0.2, 0.9, 1, 1))
        self.add_widget(title)

        resume_btn = StartButton(text="ПРОДОЛЖИТЬ", font_size=26, bold=True,
                                  size_hint=(None, None), size=(300, 75),
                                  pos_hint={"center_x": 0.5, "center_y": 0.4})
        resume_btn.bind(on_release=lambda *_: on_resume())
        self.add_widget(resume_btn)

        menu_btn = StartButton(text="В ГЛАВНОЕ МЕНЮ", font_size=22,
                                size_hint=(None, None), size=(300, 60),
                                pos_hint={"center_x": 0.5, "center_y": 0.25})
        menu_btn.bind(on_release=lambda *_: on_menu())
        self.add_widget(menu_btn)


class SettingsScreen(FloatLayout):
    def __init__(self, on_back, **kwargs):
        super().__init__(**kwargs)

        self.starfield = Starfield(self.canvas.before, lambda: (Window.width, Window.height))
        self._ev = Clock.schedule_interval(self._update, 1 / 60)

        title = Label(text="НАСТРОЙКИ", font_size=44, bold=True,
                      halign="center", valign="middle",
                      size_hint=(1, None), height=70,
                      pos_hint={"center_x": 0.5, "top": 0.95},
                      color=(0.2, 0.9, 1, 1))
        self.add_widget(title)

        scroll = ScrollView(size_hint=(None, None), size=(700, 480),
                            pos_hint={"center_x": 0.5, "center_y": 0.48})
        self.add_widget(scroll)

        box = BoxLayout(orientation="vertical", spacing=14, padding=15, size_hint_y=None)
        box.bind(minimum_height=box.setter("height"))
        scroll.add_widget(box)

        box.add_widget(self._make_label("Громкость звуков"))
        sfx_slider = Slider(min=0, max=1, value=SETTINGS.get("sfx_volume"),
                            step=0.05, size_hint=(1, None), height=40)
        sfx_slider.bind(value=lambda inst, val: SETTINGS.set("sfx_volume", val))
        box.add_widget(sfx_slider)

        box.add_widget(self._make_label("Громкость музыки"))
        music_slider = Slider(min=0, max=1, value=SETTINGS.get("music_volume"),
                              step=0.05, size_hint=(1, None), height=40)
        def on_music(inst, val):
            SETTINGS.set("music_volume", val)
            SOUND.update_volumes()
        music_slider.bind(value=on_music)
        box.add_widget(music_slider)

        box.add_widget(self._make_label("Цвет фона"))
        color_row = BoxLayout(orientation="horizontal", spacing=10,
                              size_hint=(1, None), height=50)
        self.bg_preview = Widget(size_hint=(None, None), size=(50, 40))
        self._update_bg_preview()
        color_row.add_widget(self.bg_preview)

        presets = [
            ("Чёрный", [0.01, 0.01, 0.03]),
            ("Синий", [0.02, 0.03, 0.1]),
            ("Фиолет", [0.08, 0.02, 0.12]),
            ("Зелёный", [0.02, 0.08, 0.04]),
            ("Красный", [0.1, 0.02, 0.02]),
        ]
        for name, col in presets:
            b = StartButton(text=name, font_size=12,
                            size_hint=(None, None), size=(120, 40))
            b.bind(on_release=lambda inst, c=col: self._set_bg(c))
            color_row.add_widget(b)
        box.add_widget(color_row)

        if IS_DESKTOP:
            box.add_widget(self._make_label("Управление (нажмите и введите новую клавишу)"))
            self.key_buttons = {}
            for key, label_text in [
                ("key_up", "Вверх"), ("key_down", "Вниз"),
                ("key_left", "Влево"), ("key_right", "Вправо"),
                ("key_shoot", "Стрельба"),
            ]:
                row = BoxLayout(orientation="horizontal", spacing=10,
                                size_hint=(1, None), height=45)
                row.add_widget(Label(text=label_text, size_hint=(0.4, 1),
                                      color=(1, 1, 1, 1), halign="left"))
                btn = StartButton(text=KEY_NAMES.get(SETTINGS.get(key), "?"),
                                  font_size=16, size_hint=(0.3, 1))
                btn.bind(on_release=lambda inst, k=key: self._capture_key(k))
                self.key_buttons[key] = btn
                row.add_widget(btn)
                row.add_widget(Widget())
                box.add_widget(row)
            self.waiting_key = None
        else:
            info = Label(text="На этом устройстве используется сенсорное управление\n"
                              "(экранные кнопки в игре)",
                         font_size=16, halign="center", color=(0.7, 0.9, 1, 1),
                         size_hint=(1, None), height=60)
            box.add_widget(info)
            self.waiting_key = None

        back_btn = StartButton(text="НАЗАД", font_size=22,
                                size_hint=(None, None), size=(200, 55),
                                pos_hint={"center_x": 0.5, "y": 0.02})
        back_btn.bind(on_release=lambda *_: on_back())
        self.add_widget(back_btn)

        Window.bind(on_key_down=self._on_key)

    def _make_label(self, text):
        lbl = Label(text=text, font_size=18, bold=True,
                    halign="left", valign="middle",
                    size_hint=(1, None), height=30, color=(1, 1, 0.5, 1))
        lbl.bind(size=lambda *_: setattr(lbl, "text_size", lbl.size))
        return lbl

    def _set_bg(self, color):
        SETTINGS.set("bg_color", color)
        self._update_bg_preview()
        self.starfield.refresh_bg_color()

    def _update_bg_preview(self):
        self.bg_preview.canvas.clear()
        c = SETTINGS.get("bg_color")
        with self.bg_preview.canvas:
            Color(c[0], c[1], c[2], 1)
            Rectangle(pos=self.bg_preview.pos, size=self.bg_preview.size)
            Color(1, 1, 1, 1)
            Line(rectangle=(self.bg_preview.x, self.bg_preview.y,
                            self.bg_preview.width, self.bg_preview.height), width=2)

    def _capture_key(self, setting_key):
        self.waiting_key = setting_key
        if setting_key in self.key_buttons:
            self.key_buttons[setting_key].text = "Нажми..."

    def _on_key(self, window, key, scancode, codepoint, modifiers):
        if self.waiting_key and self.waiting_key in self.key_buttons:
            SETTINGS.set(self.waiting_key, key)
            self.key_buttons[self.waiting_key].text = KEY_NAMES.get(key, str(key))
            self.waiting_key = None
            return True
        return False

    def _update(self, dt):
        self.starfield.update(dt)


class GameOverScreen(FloatLayout):
    def __init__(self, score, on_restart, on_menu, **kwargs):
        super().__init__(**kwargs)

        self.starfield = Starfield(self.canvas.before, lambda: (Window.width, Window.height))
        self._ev = Clock.schedule_interval(self._update, 1 / 60)

        title = Label(text="ИГРА ОКОНЧЕНА", font_size=48, bold=True,
                      halign="center", size_hint=(1, None), height=80,
                      pos_hint={"center_x": 0.5, "center_y": 0.72},
                      color=(1, 0.3, 0.3, 1))
        self.add_widget(title)

        score_lbl = Label(text=f"SCORE: {score}", font_size=32,
                          halign="center", size_hint=(1, None), height=60,
                          pos_hint={"center_x": 0.5, "center_y": 0.56},
                          color=(1, 1, 1, 1))
        self.add_widget(score_lbl)

        restart_btn = StartButton(text="ИГРАТЬ СНОВА", font_size=24,
                                   size_hint=(None, None), size=(280, 70),
                                   pos_hint={"center_x": 0.5, "center_y": 0.37})
        restart_btn.bind(on_release=lambda *_: on_restart())
        self.add_widget(restart_btn)

        menu_btn = StartButton(text="В ГЛАВНОЕ МЕНЮ", font_size=22,
                                size_hint=(None, None), size=(280, 60),
                                pos_hint={"center_x": 0.5, "center_y": 0.22})
        menu_btn.bind(on_release=lambda *_: on_menu())
        self.add_widget(menu_btn)

    def _update(self, dt):
        self.starfield.update(dt)


class Root(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.keys = set()
        self.state = None
        self.game_screen = None
        self.paused = False
        self.upgrade_popup = None
        self.pause_overlay = None
        self.settings_screen = None

        with self.canvas.before:
            bg = SETTINGS.get("bg_color")
            Color(bg[0], bg[1], bg[2], 1)
            self._bg_rect = Rectangle(pos=(0, 0), size=(Window.width, Window.height))

        Window.bind(on_key_down=self.on_key_down, on_key_up=self.on_key_up)
        Window.bind(on_resize=self.on_resize)
        Clock.schedule_interval(self.update, 1 / 60)
        SOUND.start_music()
        self.show_menu()

    def on_resize(self, window, w, h):
        self._bg_rect.pos = (0, 0)
        self._bg_rect.size = (w, h)

    def on_key_down(self, window, key, scancode, codepoint, modifiers):
        if key == 292:
            Window.fullscreen = not Window.fullscreen
            return True
        if key == 27:
            if self.state == "game":
                if self.paused and self.pause_overlay:
                    self.resume_game()
                elif not self.paused:
                    self.pause_game()
            return True

        if self.paused:
            return False
        self.keys.add(key)
        return False

    def on_key_up(self, window, key, scancode):
        self.keys.discard(key)

    def update(self, dt):
        if self.state == "game" and self.game_screen and not self.paused:
            self.game_screen.update(dt, self.keys)

    def exit_game(self):
        SOUND.stop_music()
        App.get_running_app().stop()
        sys.exit(0)

    def clear(self):
        if self.game_screen:
            self.game_screen.destroy_all()
            self.game_screen = None
        if self.upgrade_popup:
            self.remove_widget(self.upgrade_popup)
            self.upgrade_popup = None
        if self.pause_overlay:
            self.remove_widget(self.pause_overlay)
            self.pause_overlay = None
        if self.settings_screen:
            Window.unbind(on_key_down=self.settings_screen._on_key)
            self.settings_screen = None
        self.clear_widgets()

    def show_menu(self):
        self.clear()
        self.state = "menu"
        self.paused = False
        self.add_widget(MainMenu(on_start=self.show_game,
                                  on_settings=self.show_settings,
                                  on_exit=self.exit_game))

    def show_settings(self):
        self.clear()
        self.state = "settings"
        self.settings_screen = SettingsScreen(on_back=self.show_menu)
        self.add_widget(self.settings_screen)

    def show_game(self):
        self.clear()
        self.state = "game"
        self.paused = False
        self.game_screen = GameScreen(on_game_over=self.show_game_over,
                                       on_upgrade=self.show_upgrade)
        self.add_widget(self.game_screen)

    def pause_game(self):
        if self.paused:
            return
        self.paused = True
        self.keys.clear()
        if self.game_screen:
            self.game_screen.touch_keys.clear()
        self.pause_overlay = PauseOverlay(on_resume=self.resume_game, on_menu=self.show_menu)
        self.add_widget(self.pause_overlay)

    def resume_game(self):
        if self.pause_overlay:
            self.remove_widget(self.pause_overlay)
            self.pause_overlay = None
        self.paused = False

    def show_upgrade(self):
        if self.paused:
            return
        self.paused = True
        self.keys.clear()
        if self.game_screen:
            self.game_screen.touch_keys.clear()
            available = self.game_screen.available_abilities()
            if not available:
                self.paused = False
                return
        else:
            available = []

        self.upgrade_popup = UpgradePopup(
            on_choose=self.choose_upgrade,
            levels=self.game_screen.levels,
            available=available,
        )
        self.add_widget(self.upgrade_popup)

    def choose_upgrade(self, key):
        if self.game_screen:
            self.game_screen.apply_upgrade(key)
        if self.upgrade_popup:
            self.remove_widget(self.upgrade_popup)
            self.upgrade_popup = None
        self.paused = False

    def show_game_over(self, score):
        self.clear()
        self.state = "game_over"
        self.paused = False
        self.add_widget(GameOverScreen(score=score,
                                        on_restart=self.show_game,
                                        on_menu=self.show_menu))


class SpaceGameApp(App):
    def build(self):
        Window.fullscreen = True
        Window.show_cursor = True
        return Root()


if __name__ == "__main__":
    SpaceGameApp().run()