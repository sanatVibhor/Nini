"""Nini - a tiny orange desktop cat with moods, habits, mischief and spooky facts.

    nini wake          Nini shows up
    nini sleep         Nini says goodnight and leaves
    nini status        is she around? how is she feeling?
    nini feed          give her a treat (also in her right-click menu)
"""
import ctypes
import datetime
import json
import math
import os
import random
import subprocess
import sys
import threading
import time
import traceback
from ctypes import wintypes
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

STATE_DIR = Path.home() / ".nini"
PID_FILE = STATE_DIR / "nini.pid"
STOP_FILE = STATE_DIR / "nini.stop"
CMD_FILE = STATE_DIR / "nini.cmd"
PET_FILE = STATE_DIR / "pet.json"
LOG_FILE = STATE_DIR / "nini.log"

# --------------------------------------------------------------------------
# Words
# --------------------------------------------------------------------------
FACTS = [
    "Cats can see in near-darkness. So yes, I can see what is standing behind you.",
    "As you fall asleep, your brain can show you shadowy figures that are not really there.",
    "During sleep paralysis you wake up unable to move, and many people sense a presence in the room.",
    "Cotard's delusion is a rare condition where people believe they are already dead.",
    "In 1518, a 'dancing plague' in Strasbourg made hundreds of people dance for days. Some reportedly collapsed and died.",
    "The Winchester Mystery House has staircases that lead to ceilings and doors that open onto brick walls.",
    "In 1872 the ship Mary Celeste was found drifting at sea, fully stocked, with no one on board.",
    "Stare at your face in a mirror in dim light for a few minutes. It starts to warp into strangers and monsters.",
    "The Paris catacombs hold the bones of around six million people.",
    "Capgras delusion: a person becomes convinced their loved ones were replaced by identical impostors.",
    "The Black Death wiped out roughly a third to half of Europe in just a few years.",
    "Victorians sometimes posed for photos with their dead relatives, propped up as if alive.",
    "I can hear sounds up to about 64 kHz. Your house is much noisier at night than you think.",
    "A group of crows is called a murder. A group of ravens is called an unkindness.",
    "In 1986, Lake Nyos silently released a cloud of CO2 overnight and suffocated about 1,700 people.",
    "In 1959, nine hikers fled their tent at Dyatlov Pass in freezing night, barely dressed. Why is still debated.",
    "A parasite called Cymothoa exigua eats a fish's tongue and then lives in its mouth as a replacement.",
    "Zombie-ant fungus takes over an ant's body and makes it climb a leaf and clamp down before it dies.",
    "Tiny Demodex mites live in the pores of your face. Almost everyone has them.",
    "Around Chernobyl, a pine forest turned rust-red after absorbing deadly radiation. It is called the Red Forest.",
    "Some towns report a low, constant 'hum' that only certain people can hear and no microphone can record.",
    "An engineer once blamed a lab 'ghost' on a 19 Hz sound wave, too low to hear but enough to make you uneasy.",
    "Old vampire panic: corpses bloat and bleed from the mouth as they decay, so they looked 'alive' when dug up.",
    "Hypnic jerks, that falling feeling when you drift off, may be your brain mistaking sleep for dying.",
    "Your brain fills in the dark with its worst guesses. It is why a coat on a chair can become a person.",
    "Medieval 'sin-eaters' were paid to eat a meal over a corpse and take on the dead person's sins.",
    "Cats purr at 25 to 150 Hz, a range linked to healing. Perfectly innocent. Probably.",
    "Some deep-sea anglerfish males fuse to a female's body and slowly merge into her.",
    "The 'uncanny valley': things that look almost human, but not quite, trigger a deep sense of dread.",
]
GREETINGS = ["Meow! Nini is here.", "Nini has arrived. Did you miss me?", "Mrrp! Ready to haunt your screen."]
SPOOKY_GREETINGS = ["The shadows feel extra alive today. Meow.", "Spooky mood: ON. Stay close to me."]
SULK_LINES = ["...Oh. You're back. I wasn't waiting.", "Hmph. Look who remembered I exist."]
BYES = ["Nighty night... I'll be in the shadows.", "Bye bye! Nini goes back to the dark.", "Mew. Off to nap. Don't look under the bed."]
PET_LINES = ["prrrr...", "purrrr", "mrrp!", "*headbutt*", "prrrt?"]
PROUD_LINES = ["Got it!", "Mine.", "*proud cat noises*", "Pounce successful."]
GRUMPY_PET = ["...no.", "Hmph. Not now.", "*tail flick*"]


# --------------------------------------------------------------------------
# Small persistence helpers
# --------------------------------------------------------------------------
def load_json(path, default):
    try:
        data = json.loads(Path(path).read_text())
        return {**default, **data}
    except (OSError, ValueError):
        return dict(default)


def save_json(path, data):
    try:
        STATE_DIR.mkdir(exist_ok=True)
        Path(path).write_text(json.dumps(data))
    except OSError:
        pass


def log(msg):
    try:
        STATE_DIR.mkdir(exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(time.strftime("%H:%M:%S ") + msg + "\n")
    except OSError:
        pass




# --------------------------------------------------------------------------
# Windows helpers (idle time, finding windows to sit on)
# --------------------------------------------------------------------------
user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi
kernel32 = ctypes.windll.kernel32
kernel32.GetTickCount.restype = ctypes.c_uint
for _fn, _args, _res in (
    ("IsWindowVisible", [wintypes.HWND], wintypes.BOOL),
    ("IsWindow", [wintypes.HWND], wintypes.BOOL),
    ("IsIconic", [wintypes.HWND], wintypes.BOOL),
    ("IsZoomed", [wintypes.HWND], wintypes.BOOL),
    ("GetWindowRect", [wintypes.HWND, ctypes.c_void_p], wintypes.BOOL),
    ("GetWindowLongW", [wintypes.HWND, ctypes.c_int], ctypes.c_long),
    ("GetWindowTextLengthW", [wintypes.HWND], ctypes.c_int),
    ("GetWindowTextW", [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int], ctypes.c_int),
    ("SetWindowPos", [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT], wintypes.BOOL),
    ("GetForegroundWindow", [], wintypes.HWND),
    ("WindowFromPoint", [wintypes.POINT], wintypes.HWND),
    ("GetAncestor", [wintypes.HWND, wintypes.UINT], wintypes.HWND),
):
    getattr(user32, _fn).argtypes = _args
    getattr(user32, _fn).restype = _res
dwmapi.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]


class _LII(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def idle_seconds():
    lii = _LII()
    lii.cbSize = ctypes.sizeof(_LII)
    user32.GetLastInputInfo(ctypes.byref(lii))
    return ((kernel32.GetTickCount() - lii.dwTime) & 0xFFFFFFFF) / 1000.0


def ext_rect(hwnd):
    """Visible window bounds (without the invisible resize border)."""
    r = wintypes.RECT()
    if dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(r), ctypes.sizeof(r)) != 0:
        user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def raw_pos(hwnd):
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top


def move_window(hwnd, x, y):
    user32.SetWindowPos(hwnd, None, int(x), int(y), 0, 0, 0x0001 | 0x0004 | 0x0010)  # NOSIZE|NOZORDER|NOACTIVATE


def window_ok(hwnd):
    return bool(user32.IsWindow(hwnd) and user32.IsWindowVisible(hwnd)
                and not user32.IsIconic(hwnd) and not user32.IsZoomed(hwnd))


def list_windows():
    """Normal, visible, un-maximised app windows: [(hwnd, title, (l, t, r, b))]."""
    found = []

    def cb(h, _):
        try:
            if not window_ok(h):
                return True
            ex = user32.GetWindowLongW(h, -20)
            if ex & 0x80 or ex & 0x08000000:  # TOOLWINDOW / NOACTIVATE
                return True
            cloaked = wintypes.DWORD(0)
            dwmapi.DwmGetWindowAttribute(h, 14, ctypes.byref(cloaked), 4)
            if cloaked.value or user32.GetWindowTextLengthW(h) == 0:
                return True
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(h, buf, 256)
            if buf.value in ("Nini", "NiniBall", "Program Manager"):
                return True
            rect = ext_rect(h)
            if rect[2] - rect[0] < 300 or rect[3] - rect[1] < 150:
                return True
            found.append((h, buf.value, rect))
        except Exception:
            pass
        return True

    proto = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows(proto(cb), 0)
    return found


# --------------------------------------------------------------------------
# The cat: real pixel art on a 72x53 grid, drawn in code (no image assets).
# All body parts merge into ONE silhouette with ONE 1px outline, so legs grow
# straight out of the body (no jointed-toy seams). Only the head gets a soft
# edge where it overlaps the body. Eyes, nose, mouth and jhumkas are placed
# pixel by pixel.
# --------------------------------------------------------------------------
GW, GH = 72, 53
SUB = 8                      # sub-pixel accuracy used when rasterising shapes
INK = (34, 22, 24, 255)      # outline
ORG = (242, 146, 52, 255)    # fur
DK = (212, 100, 32, 255)     # stripes / soft edges
SHADE = (220, 118, 40, 255)  # far-side legs
WHT = (255, 247, 238, 255)
WHT_SH = (232, 216, 206, 255)
INNER = (246, 168, 178, 255)
PINK = (236, 116, 138, 255)
BLUSH = (246, 184, 184, 255)
STEEL = (188, 196, 208, 255)
STEEL_D = (126, 134, 150, 255)
STEEL_L = (238, 242, 248, 255)
WALK_AMP, RUN_AMP = 4, 6     # how far paws swing (art pixels)
N4 = ((1, 0), (-1, 0), (0, 1), (0, -1))


# ---- shapes (in art-pixel coordinates, floats welcome)
def E(x0, y0, x1, y1):
    return lambda d, s: d.ellipse([round(x0 * s), round(y0 * s), round(x1 * s), round(y1 * s)], fill=255)


def P(pts):
    return lambda d, s: d.polygon([(round(x * s), round(y * s)) for x, y in pts], fill=255)


def L(pts, w):
    """Thick rounded stroke."""
    def f(d, s):
        q = [(round(x * s), round(y * s)) for x, y in pts]
        d.line(q, fill=255, width=max(1, round(w * s)), joint="curve")
        r = w * s / 2
        for x, y in q:
            d.ellipse([x - r, y - r, x + r, y + r], fill=255)
    return f


def U(*shapes):
    def f(d, s):
        for sh in shapes:
            sh(d, s)
    return f


def gmask(shape):
    """Rasterise a shape onto the pixel grid: a pixel is in if at least half covered."""
    big = Image.new("L", (GW * SUB, GH * SUB), 0)
    shape(ImageDraw.Draw(big), SUB)
    small = big.resize((GW, GH), Image.BOX)
    return {(i % GW, i // GW) for i, v in enumerate(small.getdata()) if v >= 128}


def ring(m):
    return {(x + dx, y + dy) for x, y in m for dx, dy in N4} - m


def soft_edge(under):
    """Edge colour where the head sits on the body: pink over the white chest, dark orange over fur."""
    return BLUSH if under == WHT else DK


class Pix:
    def __init__(self):
        self.c = {}        # (x, y) -> colour
        self.sil = set()   # pixels that belong to the cat's body

    def solid(self, shape, color, edge=None, edge_on=None):
        """Add a body part. It merges into the silhouette; `edge` draws a soft line where it overlaps."""
        m = {p for p in gmask(shape) if p[1] < GH - 1}  # keep the bottom row free for the outline
        if edge:
            for p in ring(m) & (self.sil if edge_on is None else edge_on):
                self.c[p] = edge(self.c.get(p)) if callable(edge) else edge
        for p in m:
            self.c[p] = color
        self.sil |= m
        return m

    def paint(self, shape, color, clip=None):
        m = gmask(shape) & (self.sil if clip is None else clip)
        for p in m:
            self.c[p] = color
        return m

    def overlay(self, shape, color):
        """A part in front of everything (a raised paw): outlined on its own."""
        m = {p for p in gmask(shape) if p[1] < GH - 1}
        for p in ring(m):
            self.c[p] = INK
        for p in m:
            self.c[p] = color
        return m

    def put(self, pts, color, clip=None):
        for p in pts:
            if clip is None or p in clip:
                self.c[p] = color

    def line(self, x0, y0, x1, y1, color, clip=None):
        n = max(abs(x1 - x0), abs(y1 - y0), 1)
        self.put({(round(x0 + (x1 - x0) * t / n), round(y0 + (y1 - y0) * t / n)) for t in range(n + 1)}, color, clip)

    def stamp(self, x0, y0, rows, pal):
        for j, row in enumerate(rows):
            for i, ch in enumerate(row):
                if ch in pal:
                    self.c[(x0 + i, y0 + j)] = pal[ch]

    def outline(self):
        for p in ring(self.sil):
            self.c[p] = INK

    def image(self):
        img = Image.new("RGBA", (GW, GH), (0, 0, 0, 0))
        px = img.load()
        for (x, y), col in self.c.items():
            if 0 <= x < GW and 0 <= y < GH:
                px[x, y] = col
        return img


# ---- eyes: big and shiny, hand-placed pixels ('#' ink, 'w' white)
EYES6 = {
    "open":   [".####.", "#ww###", "#ww###", "######", "####w#", ".####."],
    "wide":   [".####.", "#www##", "#ww###", "######", "###ww#", ".####."],
    "half":   ["......", "......", "######", "######", "####w#", ".####."],
    "happy":  ["......", "......", ".####.", "#....#", "......", "......"],
    "closed": ["......", "......", "......", "#....#", ".####.", "......"],
    "blink":  ["......", "......", "......", "######", "......", "......"],
}
EYES5 = {
    "open":   [".###.", "#ww##", "#w###", "#####", "###w#", ".###."],
    "wide":   [".###.", "#ww##", "#ww##", "#####", "###w#", ".###."],
    "half":   [".....", ".....", "#####", "#####", "###w#", ".###."],
    "happy":  [".....", ".....", ".###.", "#...#", ".....", "....."],
    "closed": [".....", ".....", ".....", "#...#", ".###.", "....."],
    "blink":  [".....", ".....", ".....", "#####", ".....", "....."],
}
EYES7 = {  # the big front-facing eyes
    "open":   [".#####.", "#ww####", "#ww####", "#######", "#######", "####w##", ".#####."],
    "wide":   [".#####.", "#www###", "#ww####", "#######", "#######", "###ww##", ".#####."],
    "half":   [".......", ".......", "#######", "#######", "#######", "####w##", ".#####."],
    "happy":  [".......", ".......", ".#####.", "#.....#", ".......", ".......", "......."],
    "closed": [".......", ".......", ".......", "#.....#", ".#####.", ".......", "......."],
    "blink":  [".......", ".......", ".......", "#######", ".......", ".......", "......."],
}
EYE_PAL = {"#": INK, "w": WHT}

# ---- jhumka: a little steel bell earring, soft grey outline so it sits in the fur
JHUMKA = [".dsd.", "dslsd", "dsssd", "ddddd", "s.s.s"]
JH_PAL = {"d": STEEL_D, "s": STEEL, "l": STEEL_L}


def jhumka(px, ax, ay, side=-1, sw=0):
    """Hang a jhumka from the ear base (ax, ay); it dangles outward (side -1 = left, +1 = right)."""
    cx = ax + 3 * side + sw
    px.put({(ax, ay), (ax + side, ay + 1)}, STEEL_D)  # little chain
    for j, row in enumerate(JHUMKA):
        for i, ch in enumerate(row):
            if ch in JH_PAL:
                px.c[(cx - 2 + i, ay + 2 + j)] = JH_PAL[ch]


def swing(t):
    return round(1.2 * math.sin(t))


# ---- heads
def head_front(px, eye="open", ears="up", on_body=True):
    """Head facing you, centred on the sprite (mirror axis between columns 35|36)."""
    head = px.solid(U(E(20, 4.5, 52, 29), E(16.5, 12, 55.5, 34),
                      P([(18.5, 23), (13.5, 27.5), (19, 30)]), P([(53.5, 23), (58.5, 27.5), (53, 30)])),
                    ORG, edge=soft_edge if on_body else None)
    if ears == "flat":
        px.solid(P([(20, 15), (7, 9), (28, 8)]), ORG)
        px.solid(P([(52, 15), (65, 9), (44, 8)]), ORG)
    else:
        el = px.solid(P([(19, 16), (19.5, 0.8), (31, 8)]), ORG)
        er = px.solid(P([(53, 16), (52.5, 0.8), (41, 8)]), ORG)
        px.paint(P([(21.6, 12), (21.8, 4), (28, 8.4)]), INNER, clip=el)
        px.paint(P([(50.4, 12), (50.2, 4), (44, 8.4)]), INNER, clip=er)
        px.put({(23, 9), (48, 9)}, WHT)
    px.paint(U(E(21, 22, 51, 37), P([(33, 23), (36, 13), (39, 23)])), WHT, clip=head)
    px.put({(35, 6), (36, 6), (35, 7), (36, 7), (35, 8), (36, 8),
            (30, 7), (30, 8), (31, 9), (41, 7), (41, 8), (40, 9)}, DK, clip=head)
    px.put({(18, 20), (19, 20), (20, 20), (18, 23), (19, 23),
            (53, 20), (52, 20), (51, 20), (53, 23), (52, 23)}, DK, clip=head)
    px.stamp(22, 15, EYES7[eye], EYE_PAL)
    px.stamp(43, 15, EYES7[eye], EYE_PAL)
    if eye in ("open", "wide"):
        px.put({(26, 13), (45, 13)}, WHT)
    px.put({(34, 23), (35, 23), (36, 23), (37, 23), (35, 24), (36, 24)}, PINK)
    px.put({(33, 25), (35, 25), (36, 25), (38, 25), (34, 26), (37, 26)}, INK)
    px.put({(22, 24), (23, 24), (48, 24), (49, 24)}, BLUSH)


def front_extras(px, sw=0, whiskers=True):
    """Drawn after the outline: whiskers and jhumkas hang outside the silhouette."""
    if whiskers:
        px.line(16, 24, 10, 23, INK)
        px.line(16, 27, 10, 28, INK)
        px.line(55, 24, 61, 23, INK)
        px.line(55, 27, 61, 28, INK)
    jhumka(px, 18, 15, -1, sw)
    jhumka(px, 53, 15, 1, sw)


def head_3q(px, cx, cy, eye="open", ears="up"):
    """Head turned three-quarters to the right (walking, loafing, sleeping)."""
    head = px.solid(U(E(cx - 12.5, cy - 14.5, cx + 13.5, cy + 10), E(cx - 15, cy - 7, cx + 15, cy + 14),
                      P([(cx - 13.5, cy + 4), (cx - 18, cy + 8.5), (cx - 12.5, cy + 11)])), ORG, edge=soft_edge)
    if ears == "flat":
        px.solid(P([(cx - 10, cy - 7), (cx - 20, cy - 12), (cx - 3, cy - 13)]), ORG)
        px.solid(P([(cx + 4, cy - 13), (cx + 19, cy - 14), (cx + 13, cy - 6)]), ORG)
    else:
        eb = px.solid(P([(cx - 11.5, cy - 6), (cx - 11, cy - 19), (cx - 2, cy - 12)]), ORG)
        ef = px.solid(P([(cx + 3, cy - 12), (cx + 11.5, cy - 19), (cx + 13.5, cy - 5)]), ORG)
        px.paint(P([(cx - 9.5, cy - 9), (cx - 9.3, cy - 16), (cx - 4.5, cy - 12)]), INNER, clip=eb)
        px.paint(P([(cx + 5, cy - 12), (cx + 10.5, cy - 16), (cx + 11.5, cy - 8)]), INNER, clip=ef)
    px.paint(U(E(cx - 2.5, cy + 0.5, cx + 11.5, cy + 13), P([(cx + 1.6, cy), (cx + 4, cy - 8), (cx + 6.4, cy)])), WHT, clip=head)
    px.put({(cx + 2, cy - 13), (cx + 3, cy - 13), (cx + 2, cy - 12), (cx + 3, cy - 12),
            (cx - 3, cy - 12), (cx - 3, cy - 11), (cx - 2, cy - 10), (cx + 8, cy - 12), (cx + 8, cy - 11), (cx + 7, cy - 10),
            (cx - 14, cy + 1), (cx - 13, cy + 1), (cx - 12, cy + 1), (cx - 14, cy + 4), (cx - 13, cy + 4)}, DK, clip=head)
    px.stamp(cx - 6, cy - 5, EYES6[eye], EYE_PAL)
    px.stamp(cx + 6, cy - 5, EYES5[eye], EYE_PAL)
    if eye in ("open", "wide"):
        px.put({(cx - 2, cy - 7)}, WHT)
    px.put({(cx + 2, cy + 1), (cx + 3, cy + 1), (cx + 4, cy + 1), (cx + 5, cy + 1), (cx + 3, cy + 2), (cx + 4, cy + 2)}, PINK)
    px.put({(cx + 1, cy + 3), (cx + 3, cy + 3), (cx + 4, cy + 3), (cx + 6, cy + 3), (cx + 2, cy + 4), (cx + 5, cy + 4)}, INK)
    px.put({(cx - 8, cy + 2), (cx - 7, cy + 2), (cx + 11, cy + 2)}, BLUSH, clip=head)


def extras_3q(px, cx, cy, sw=0):
    px.line(cx + 14, cy + 2, cx + 19, cy + 1, INK)
    px.line(cx + 14, cy + 5, cx + 19, cy + 6, INK)
    jhumka(px, cx - 12, cy - 7, -1, sw)


# ---- poses
def sit_front(i=0, eye="open", ears="up", arm=None, a=0):
    """Sitting and facing you (the reference pose)."""
    px = Pix()
    t = i * 2 * math.pi / 12
    w = round(1.5 * math.sin(t))
    tail = px.solid(L([(44, 50), (53, 49.5), (57, 44), (56.5 + w, 37)], 4.4), ORG)
    px.paint(E(53 + w, 33, 60 + w, 39.5), WHT, clip=tail)
    px.solid(E(21, 25, 51, 53), ORG, edge=INK, edge_on=tail)
    px.solid(E(18.5, 38, 35, 53), ORG)
    px.solid(E(37, 38, 53.5, 53), ORG)
    px.paint(U(E(28.5, 25, 43.5, 38), P([(28.8, 32), (43.2, 32), (38.6, 53), (33.4, 53)])), WHT)
    for lx in (31, 41):  # stubby front legs, same fur as the body
        leg = px.solid(L([(lx, 38), (lx, 49.5)], 6.4), ORG)
        px.paint(E(lx - 3.6, 47.5, lx + 3.6, 54), WHT, clip=leg)
    px.line(27, 42, 27, 47, DK)
    px.line(44, 42, 44, 47, DK)
    for (x0, y0, x1, y1) in ((20, 43, 23, 42), (20, 47, 23, 46), (23, 32, 25, 33), (22, 36, 24, 37)):
        px.line(x0, y0, x1, y1, DK, clip=px.sil)
        px.line(71 - x0, y0, 71 - x1, y1, DK, clip=px.sil)
    head_front(px, eye, ears)
    px.outline()
    if arm == "groom":  # paw up to wash her face
        m = px.overlay(U(L([(44, 44), (42, 30 + a)], 6), E(38, 24 + a, 46.5, 31 + a)), ORG)
        px.paint(E(38, 24 + a, 46.5, 30 + a), WHT, clip=m)
    elif arm == "swat":  # paw stretched out to bat something
        m = px.overlay(U(L([(44, 42), (56 + 2 * a, 35 - 2 * a)], 6), E(53 + 2 * a, 31 - 2 * a, 61 + 2 * a, 38 - 2 * a)), ORG)
        px.paint(E(54 + 2 * a, 31 - 2 * a, 61 + 2 * a, 38 - 2 * a), WHT, clip=m)
    front_extras(px, swing(t))
    return px.image()


def back(i=0):
    """Sitting with her back to you, tail swishing."""
    px = Pix()
    t = i * 2 * math.pi / 12
    w = round(2.2 * math.sin(t))
    tail = px.solid(L([(46, 50), (55, 49.5), (59, 43), (58.5 + w, 35)], 4.4), ORG)
    px.paint(E(55 + w, 31, 62 + w, 37.5), WHT, clip=tail)
    body = px.solid(E(21, 25, 51, 53), ORG, edge=INK, edge_on=tail)
    px.solid(E(18.5, 38, 35, 53), ORG)
    px.solid(E(37, 38, 53.5, 53), ORG)
    for y in (31, 36, 41, 46):
        px.line(25, y, 30, y + 1, DK, clip=px.sil)
        px.line(46, y, 41, y + 1, DK, clip=px.sil)
    head = px.solid(E(17.5, 5, 54.5, 34), ORG, edge=DK, edge_on=body)
    px.solid(P([(19, 16), (19.5, 0.8), (31, 8)]), ORG)
    px.solid(P([(53, 16), (52.5, 0.8), (41, 8)]), ORG)
    px.put({(35, 6), (36, 6), (35, 7), (36, 7), (35, 8), (36, 8), (35, 9), (36, 9),
            (30, 8), (30, 9), (31, 10), (41, 8), (41, 9), (40, 10)}, DK, clip=head)
    px.outline()
    jhumka(px, 18, 15, -1, swing(t))
    jhumka(px, 53, 15, 1, swing(t))
    return px.image()


def side(bd=0, tilt=0, hx=0, hd=0, legs=None, tail_p=0.0, tail_up=0, eye="open", ears="up"):
    """Walking / running / crouching, in profile facing right with the head turned to you."""
    px = Pix()
    legs = legs or [(0, 0)] * 4  # back_far, front_far, back_near, front_near: (dx, lift)
    br, bf = bd, bd + tilt
    w = 1.6 * math.sin(tail_p)
    tail = px.solid(L([(13, 30 + br), (7, 28 + br), (4.5, 21 + br - tail_up), (6.5 + w, 14 + br - tail_up)], 4.4), ORG)
    px.paint(E(3 + w, 10 + br - tail_up, 10 + w, 17 + br - tail_up), WHT, clip=tail)

    def leg(k, x, color, paw):
        dx, lift = legs[k]
        hy = 37 + (br if k in (0, 2) else bf)
        fx, fy = x + dx, 52.5 - lift
        m = px.solid(U(P([(x - 3, hy), (x + 3, hy), (fx + 3, fy - 3.5), (fx - 3, fy - 3.5)]),
                       E(fx - 3.6, fy - 6.5, fx + 3.6, fy)), color)
        px.paint(E(fx - 4, fy - 3.4, fx + 4, fy + 2), paw, clip=m)

    leg(0, 21, SHADE, WHT_SH)
    leg(1, 39, SHADE, WHT_SH)
    torso = px.solid(U(E(9, 22 + br, 33, 43 + br), E(24, 22 + bf, 49, 43 + bf)), ORG, edge=DK, edge_on=tail)
    px.paint(U(E(14, 35 + br, 32, 45 + br), E(26, 35 + bf, 46, 45 + bf)), WHT, clip=torso)
    for x in (16, 22, 28, 34):
        b = br if x < 28 else bf
        px.line(x, 23 + b, x + 1, 27 + b, DK, clip=torso)
    px.solid(E(9, 28 + br, 24, 45 + br), ORG)  # hind thigh, merged into the body
    px.line(12, 33 + br, 15, 34 + br, DK, clip=px.sil)
    leg(2, 15, ORG, WHT)
    leg(3, 43, ORG, WHT)
    cx, cy = 52 + hx, 20 + bf + hd
    head_3q(px, cx, cy, eye, ears)
    px.outline()
    extras_3q(px, cx, cy, swing(tail_p + 1.2))
    return px.image()


def loaf(paw=0, eye="open"):
    """Loaf. paw 0/1 alternates the kneading paw, 2 = paws tucked."""
    px = Pix()
    torso = px.solid(E(4, 24, 58, 70), ORG)
    for x in (12, 18, 24, 30, 36):
        px.line(x, 26, x + 1, 30, DK, clip=torso)
    tail = px.solid(L([(6, 44), (9, 50), (24, 50.5), (36, 50)], 4.2), ORG, edge=DK)
    px.paint(E(33, 47, 40, 53), WHT, clip=tail)
    cx, cy = 50, 26
    head_3q(px, cx, cy, eye)
    ua = 2 if paw == 0 else 0
    ub = 2 if paw == 1 else 0
    px.solid(E(40, 45 - ua, 48, 53 - ua), WHT, edge=DK)
    px.solid(E(47, 45 - ub, 55, 53 - ub), WHT, edge=DK)
    px.outline()
    extras_3q(px, cx, cy, 0)
    return px.image()


def sleep(breath=0):
    px = Pix()
    torso = px.solid(E(4, 21 + breath, 60, 70), ORG)
    for x in (12, 18, 24, 30, 36):
        px.line(x, 23 + breath, x + 1, 27 + breath, DK, clip=torso)
    cx, cy = 47, 37
    head_3q(px, cx, cy, "closed")
    tail = px.solid(L([(6, 44), (10, 50), (30, 50.5), (50, 49)], 4.2), ORG, edge=DK)
    px.paint(E(47, 46, 54, 53), WHT, clip=tail)
    px.outline()
    extras_3q(px, cx, cy, 0)
    return px.image()


def make_sprite(kind, i=0, eye="open"):
    if kind in ("walk", "run"):
        run = kind == "run"
        amp, lift_h = (RUN_AMP, 3) if run else (WALK_AMP, 2)
        p = i * math.pi / 4  # 8 frames per stride
        legs = [(round(amp * math.sin(ph)), round(lift_h * max(0.0, math.cos(ph))))
                for ph in (p, p + math.pi, p + math.pi, p)]  # diagonal pairs move together
        if run:
            bd = (-1, 0, 1, 0)[i % 4]
        else:
            bd = 1 if abs(math.sin(p)) > 0.9 else 0
        return side(bd=bd, hx=1 if run else 0, legs=legs, tail_p=p, tail_up=3 if run else 1, eye=eye)
    if kind in ("sit", "front"):
        return sit_front(i, eye)
    if kind == "groom":
        return sit_front(0, "closed", arm="groom", a=i)
    if kind == "swat":
        return sit_front(0, eye, arm="swat", a=i)
    if kind == "loaf":
        return loaf(i, eye)
    if kind == "sleep":
        return sleep(i)
    if kind == "back":
        return back(i)
    if kind == "crouch":
        return side(bd=5, tilt=1, hx=2, hd=1, tail_p=i * math.pi, tail_up=3, eye="wide", ears="flat")
    if kind == "bow":  # play bow / stretch / peering over an edge
        return side(bd=-1, tilt=7, hx=3, hd=1, legs=[(0, 0), (4, 0), (0, 0), (4, 0)], tail_up=4, eye=eye)
    if kind == "jump":
        return side(bd=-3, hx=1, legs=[(-4, 2), (5, 3), (-4, 2), (5, 3)], tail_up=4, eye="wide", ears="flat")
    if kind == "hang":
        return side(bd=-2, hx=1, hd=1, tail_up=-2, eye="blink", ears="flat")
    raise ValueError(kind)


# ---- yarn ball
BALL_PINK, BALL_LIGHT = (232, 80, 100, 255), (250, 156, 172, 255)
PALETTE = [INK, BALL_PINK, BALL_LIGHT]


def pixelize(img, gw, gh, thr=110):
    """Shrink smooth art to a pixel grid and snap every pixel to the palette."""
    small = img.resize((gw, gh), Image.BOX)
    out = Image.new("RGBA", (gw, gh), (0, 0, 0, 0))
    src, dst = small.load(), out.load()
    for y in range(gh):
        for x in range(gw):
            r, g, b, a = src[x, y]
            if a < thr:
                continue
            r, g, b = (min(255, c * 255 // a) for c in (r, g, b))
            dst[x, y] = min(PALETTE, key=lambda c: (c[0] - r) ** 2 + (c[1] - g) ** 2 + (c[2] - b) ** 2)
    return out


def make_ball(angle, grid=11):
    big = 100
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([6, 6, 94, 94], fill=INK)
    d.ellipse([12, 12, 88, 88], fill=BALL_PINK)
    strands = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    sd = ImageDraw.Draw(strands)
    for box in ([4, 26, 96, 86], [20, 4, 80, 96], [-10, 10, 70, 92]):
        sd.arc(box, 200, 340, fill=BALL_LIGHT, width=12)
    inside = Image.new("L", (big, big), 0)
    ImageDraw.Draw(inside).ellipse([12, 12, 88, 88], fill=255)
    img.paste(strands, mask=ImageChops.multiply(strands.getchannel("A"), inside))
    return pixelize(img.rotate(angle, Image.BICUBIC), grid, grid)


# --------------------------------------------------------------------------
# The desktop pet
# --------------------------------------------------------------------------
def run_pet(demo=False):
    import tkinter as tk
    import tkinter.font as tkfont
    from PIL import ImageTk

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    KEY = "#010101"
    root = tk.Tk()
    root.title("Nini")
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-transparentcolor", KEY)
    root.configure(bg=KEY)

    k = root.winfo_fpixels("1i") / 96.0
    SCALE = max(2, round(150 * k / GW))  # screen pixels per art pixel
    CW, CH = GW * SCALE, GH * SCALE
    WIN_W, WIN_H = int(340 * k), CH + int(150 * k)
    WRAP = int(230 * k)

    r = wintypes.RECT()
    if not user32.SystemParametersInfoW(48, 0, ctypes.byref(r), 0):  # work area (above taskbar)
        r.left, r.top, r.right, r.bottom = 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()
    WA_L, WA_T, WA_R, WA_B = r.left, r.top, r.right, r.bottom

    now0 = datetime.datetime.now()
    SPOOKY = now0.weekday() == 4 or now0.day == 13  # Fridays and the 13th

    canvas = tk.Canvas(root, width=WIN_W, height=WIN_H, bg=KEY, highlightthickness=0, bd=0)
    canvas.pack()
    font = tkfont.Font(family="Segoe UI", size=10, weight="bold")
    big = tkfont.Font(family="Segoe UI", size=14, weight="bold")
    cat_item = canvas.create_image(0, WIN_H, anchor="s")
    cache, pil_cache = {}, {}

    def pil(kind, i, eye):
        key = (kind, i, eye)
        if key not in pil_cache:
            pil_cache[key] = make_sprite(kind, i, eye).resize((CW, CH), Image.NEAREST)
        return pil_cache[key]

    def photo(kind, i, eye, face):
        key = (kind, i, eye, face)
        if key not in cache:
            img = pil(kind, i, eye)
            if face < 0:
                img = img.transpose(Image.FLIP_LEFT_RIGHT)
            cache[key] = ImageTk.PhotoImage(img)
        return cache[key]

    def prewarm():  # draw the common frames in the background so animation never stutters
        jobs = [("sit", i, e) for e in ("open", "blink", "happy") for i in range(12)]
        jobs += [(k2, i, "open") for k2 in ("walk", "run") for i in range(8)]
        jobs += [("front", i, e) for e in ("wide", "half", "closed") for i in range(12)]
        jobs += [("back", i, "open") for i in range(12)] + [("sleep", 0, "closed"), ("sleep", 1, "closed")]
        jobs += [("groom", 0, "closed"), ("groom", 1, "closed"), ("swat", 0, "open"), ("swat", 1, "open"),
                 ("loaf", 0, "happy"), ("loaf", 1, "happy"), ("loaf", 2, "half"), ("loaf", 2, "blink"),
                 ("crouch", 0, "open"), ("crouch", 1, "open"), ("jump", 0, "open"), ("hang", 0, "open"),
                 ("bow", 0, "closed"), ("bow", 0, "open"), ("bow", 0, "happy")]
        for job in jobs:
            try:
                pil(*job)
            except Exception:
                log("prewarm error: " + traceback.format_exc())

    threading.Thread(target=prewarm, daemon=True).start()

    # ---- yarn ball (its own tiny transparent window)
    class Ball:
        def __init__(self):
            self.size = 11 * SCALE
            self.win = tk.Toplevel(root)
            self.win.title("NiniBall")
            self.win.overrideredirect(True)
            self.win.attributes("-topmost", True)
            self.win.attributes("-transparentcolor", KEY)
            self.win.configure(bg=KEY)
            self.frames = [ImageTk.PhotoImage(make_ball(a * 30).resize((self.size, self.size), Image.NEAREST)) for a in range(12)]
            self.label = tk.Label(self.win, image=self.frames[0], bd=0, bg=KEY)
            self.label.pack()
            self.win.withdraw()
            self.visible = False
            self.x, self.h, self.vx, self.vh, self.rot = 0.0, 0.0, 0.0, 0.0, 0.0

        def show(self, x):
            self.x, self.h, self.vx, self.vh = x, 0.0, 0.0, 0.0
            self.visible = True
            self.win.deiconify()
            self.place()

        def hide(self):
            self.visible = False
            self.win.withdraw()

        def kick(self, vx):
            self.vx, self.vh = vx, 7.0

        @property
        def resting(self):
            return abs(self.vx) < 0.6 and self.h <= 0.5

        def step(self):
            self.x += self.vx
            if self.h > 0 or self.vh > 0:
                self.vh -= 0.7
                self.h += self.vh
                if self.h <= 0:
                    self.h = 0.0
                    self.vh = -self.vh * 0.5 if abs(self.vh) > 2 else 0.0
            else:
                self.vx *= 0.96
            if abs(self.vx) < 0.15:
                self.vx = 0.0
            lo, hi = WA_L + self.size // 2, WA_R - self.size // 2
            if self.x < lo or self.x > hi:
                self.x = min(max(self.x, lo), hi)
                self.vx = -self.vx * 0.8
            self.rot += self.vx / (self.size / 2)

        def place(self):
            frame = self.frames[int(math.degrees(self.rot) / 30) % 12]
            self.label.configure(image=frame)
            self.win.geometry(f"{self.size}x{self.size}+{int(self.x - self.size / 2)}+{int(WA_B - self.size - self.h)}")

    class Nini:
        def __init__(self):
            pet = load_json(PET_FILE, {"affection": 60.0, "hunger": 25.0, "last_seen": time.time(), "pets": 0})
            away_h = max(0.0, (time.time() - pet["last_seen"]) / 3600)
            self.affection = max(0.0, pet["affection"] - min(40.0, away_h * 0.8))
            self.hunger = min(100.0, pet["hunger"] + min(60.0, away_h * 3))
            self.pets = pet["pets"]
            self.sulky = away_h > 20 or self.affection < 20

            self.x = WA_L - CW
            self.fy = WA_B
            self.floor, self.minx, self.maxx = WA_B, WA_L + CW // 2, WA_R - CW // 2
            self.perch = None
            self.vx = self.vy = 0.0
            self.face = 1
            self.n = 0
            self.blink = 0
            self.bubble = None  # (text, until)
            self.next_fact = time.time() + (10 if not SPOOKY else 8)
            self.happy_until = 0.0
            self.last_nap = time.time()
            self.fx = []
            self.tx, self.speed, self.zoom = self.x, 2.0, 0
            self.after_walk = None
            self.land_line = None
            self.press, self.dragging = None, False
            self.queued = None
            self.idle_sleep = False
            self.idle_done = False
            self.ign_clicks = 0
            self.bat_t = 0
            self.play_hits, self.play_t0, self.ball_hide_at = 0, 0.0, 0.0
            self.jt = None
            self.nudge = None      # {'hwnd','orig','cur','restore_at'}
            self.win_anim = None   # {'hwnd','a','b','i','n'}
            self.last_save = time.time()
            self.last_hunger_msg = time.time()
            self.said_3am = False
            self.errors = 0
            self.dead = False
            self.travel, self.last_x = 0.0, self.x
            self.hover_until = 0.0
            self.ball = Ball()
            self.demo_i, self.demo_t = int(os.environ.get("NINI_DEMO_START", 0)), time.time() + 8
            self.go("enter")
            if self.sulky:
                self.say(random.choice(SULK_LINES), 5)
            elif SPOOKY:
                self.say(random.choice(SPOOKY_GREETINGS), 5)
            else:
                self.say(random.choice(GREETINGS), 4)

        # ---- helpers
        def go(self, state, dur=0.0):
            self.state, self.t0, self.dur = state, time.time(), dur

        def say(self, text, secs=None):
            self.bubble = (text, time.time() + (secs or len(text) * 0.07 + 3.5))

        def cursor(self):
            return root.winfo_pointerx(), root.winfo_pointery()

        def clamp_x(self):
            self.x = min(max(self.x, self.minx), self.maxx)

        def ground(self):
            self.perch = None
            self.floor, self.minx, self.maxx = WA_B, WA_L + CW // 2, WA_R - CW // 2

        def mood(self):
            if self.affection < 25:
                return "sulky"
            if self.hunger > 75:
                return "hungry and grumpy"
            if self.affection > 70 and self.hunger < 50:
                return "very happy"
            return "content"

        def save(self):
            save_json(PET_FILE, {"affection": self.affection, "hunger": self.hunger,
                                 "last_seen": time.time(), "pets": self.pets})

        def walk_to(self, tx, speed, after=None):
            self.tx = min(max(tx, self.minx), self.maxx)
            self.speed, self.after_walk = speed, after
            self.go("walk")

        def random_x(self):
            tx = self.x
            for _ in range(10):
                tx = random.randint(int(self.minx), int(self.maxx))
                if abs(tx - self.x) > 200:
                    break
            return tx

        # ---- actions (used by the random chooser, menu, queue and demo)
        def do(self, name):
            now = time.time()
            ground_only = {"run", "zoomies", "chase", "hop", "ball", "perch"}
            if self.perch and name in ground_only - {"hop", "run"}:
                self.queued = name
                self.descend()
                return
            h = datetime.datetime.now().hour
            if name == "walk":
                self.walk_to(self.random_x(), 1.5 if 13 <= h < 17 else 2.0)
            elif name == "run":
                self.walk_to(self.random_x(), 6.0)
            elif name == "zoomies":
                self.zoom = random.randint(2, 4)
                self.walk_to(self.random_x(), 8.0)
            elif name == "chase":
                cx, _ = self.cursor()
                self.face = 1 if cx > self.x else -1
                self.go("stare", 1.3)
            elif name == "hop":
                self.vx, self.vy = random.choice((-3, 3)), -9
                self.face = 1 if self.vx > 0 else -1
                self.land_line = None
                self.go("pounce")
            elif name == "nap":
                self.last_nap = now
                self.go("sleep", random.uniform(15, 30))
            elif name == "groom":
                self.go("groom", random.uniform(5, 8))
            elif name == "stretch":
                self.go("stretch", 2.8)
            elif name == "knead":
                self.go("knead", 5.0)
            elif name == "loaf":
                self.go("loaf", random.uniform(8, 15))
            elif name == "slowblink":
                self.go("slowblink", 2.6)
            elif name == "ignore":
                self.ign_clicks = 0
                self.go("ignore", random.uniform(8, 14) if self.affection > 25 else random.uniform(15, 25))
            elif name == "ball":
                self.start_play()
            elif name == "perch":
                if not self.start_perch():
                    self.go("sit", 2)
            elif name == "swat":
                self.go("swat", 2.0)
            elif name == "descend":
                self.descend()
            elif name == "peek":
                edge = self.minx if self.x - self.minx < self.maxx - self.x else self.maxx
                self.walk_to(edge, 2.0, "peek")
            elif name == "hungry":
                self.say("Feed me. (Right-click me for a treat.)", 5)
                self.go("sit", 3)
            elif name == "fact":
                self.say(random.choice(FACTS))
                self.go("sit", 0)
            elif name == "treat":
                self.give_treat()
            else:
                self.go("sit", random.uniform(2, 5))

        def choose_next(self):
            now = time.time()
            if self.queued:
                name, self.queued = self.queued, None
                return self.do(name)
            if idle_seconds() > 90 and not self.perch and not self.idle_done:
                self.idle_done = True
                cx, _ = self.cursor()
                self.walk_to(cx + (-120 if self.x < cx else 120), 2.5, "idle_sleep")
                return
            h = datetime.datetime.now().hour
            night = h >= 22 or h < 5
            sleepy = 13 <= h < 17
            morning = 6 <= h < 11
            cx, _ = self.cursor()
            perched = self.perch is not None
            fg = user32.GetForegroundWindow()
            w = {"walk": 24 * (0.7 if sleepy else 1), "sit": 6, "groom": 10, "loaf": 6 * (2 if sleepy else 1),
                 "stretch": 6 * (3 if morning else 1), "knead": 4,
                 "slowblink": 4 * (2 if self.affection > 60 else 1),
                 "ignore": 4 * (6 if self.affection < 25 else 1),
                 "nap": (6 * (4 if sleepy else 0.4 if night else 1)) if now - self.last_nap > 90 else 0,
                 "hop": 6, "run": 8 * (2 if night else 1)}
            if self.hunger > 70:
                w["hungry"] = 8
            if not perched:
                w["zoomies"] = 4 * (4 if night else 0.3 if sleepy else 1)
                w["chase"] = 10 if abs(cx - self.x) > 250 else 0
                w["ball"] = 5 * (0.5 if sleepy else 1)
                w["perch"] = 6
            else:
                w["descend"] = 8
                w["peek"] = 4
                w["swat"] = 3 if self.perch != fg else 0
            names = [n for n, v in w.items() if v > 0]
            self.do(random.choices(names, [w[n] for n in names])[0])

        # ---- perching on windows
        def start_perch(self):
            wins = []
            for hwnd, title, (l, t, rr, b) in list_windows():
                height = WA_B - t
                if 80 <= height <= 700 and rr - l >= CW + 60 and l < WA_R and rr > WA_L:
                    pt = wintypes.POINT((l + rr) // 2, t + 4)
                    top = user32.WindowFromPoint(pt)
                    if top and user32.GetAncestor(top, 2) == hwnd:  # its title bar is actually visible
                        wins.append((hwnd, l, t, rr))
            if not wins:
                return False
            fg = user32.GetForegroundWindow()
            pref = [wn for wn in wins if wn[0] == fg]
            hwnd, l, t, rr = random.choice(pref if pref and random.random() < 0.5 else wins)
            lo, hi = max(l, WA_L) + CW // 2 + 10, min(rr, WA_R) - CW // 2 - 10
            if lo >= hi:
                return False
            self.jump_to(random.randint(lo, hi), t, hwnd)
            return True

        def jump_to(self, tx, ty, perch):
            g = 0.9
            apex = min(self.fy, ty) - 30
            vy0 = -math.sqrt(2 * g * (self.fy - apex))
            total = -vy0 / g + math.sqrt(2 * (ty - apex) / g)
            self.vy = vy0
            self.vx = (tx - self.x) / max(total, 1)
            self.face = 1 if tx > self.x else -1
            self.jt = {"tx": tx, "ty": ty, "perch": perch}
            self.go("jump_to")

        def descend(self):
            lo, hi = WA_L + CW // 2, WA_R - CW // 2
            tx = min(max(self.x + random.randint(-120, 120), lo), hi)
            self.jump_to(tx, WA_B, None)

        def drop(self, line="Whoa!"):
            self.ground()
            self.vx = self.vy = 0.0
            self.land_line = line
            self.go("pounce")

        def track_perch(self):
            if not self.perch or self.state in ("jump_to", "pounce", "drag", "goodbye"):
                return
            if not window_ok(self.perch):
                return self.drop()
            l, t, rr, _ = ext_rect(self.perch)
            self.floor, self.minx, self.maxx = t, max(l, WA_L) + CW // 2, min(rr, WA_R) - CW // 2
            if self.minx >= self.maxx:
                return self.drop()
            self.fy = self.floor

        # ---- window nudging (she bats it, later puts it back)
        def do_nudge(self):
            if self.nudge or not self.perch or not window_ok(self.perch):
                return
            hwnd = self.perch
            x, y = raw_pos(hwnd)
            l, t, rr, b = ext_rect(hwnd)
            dx = random.choice((-1, 1)) * random.randint(40, 70)
            if l + dx < WA_L or rr + dx > WA_R:
                dx = -dx
            dy = random.randint(0, 20) if b + 20 < WA_B else 0
            self.nudge = {"hwnd": hwnd, "orig": (x, y), "cur": (x + dx, y + dy), "restore_at": time.time() + random.uniform(6, 10)}
            self.win_anim = {"hwnd": hwnd, "a": (x, y), "b": (x + dx, y + dy), "i": 0, "n": 14}
            self.say("Oops. *innocent face*", 3)

        def tick_window_stuff(self, now):
            wa = self.win_anim
            if wa:
                wa["i"] += 1
                t = wa["i"] / wa["n"]
                e = 1 - (1 - t) ** 3
                if user32.IsWindow(wa["hwnd"]):
                    move_window(wa["hwnd"], wa["a"][0] + (wa["b"][0] - wa["a"][0]) * e, wa["a"][1] + (wa["b"][1] - wa["a"][1]) * e)
                if wa["i"] >= wa["n"]:
                    self.win_anim = None
                    if self.nudge and self.nudge.get("restoring"):
                        self.nudge = None
            nd = self.nudge
            if nd and not self.win_anim and not nd.get("restoring") and now >= nd["restore_at"]:
                if user32.IsWindow(nd["hwnd"]):
                    px, py = raw_pos(nd["hwnd"])
                    if abs(px - nd["cur"][0]) < 8 and abs(py - nd["cur"][1]) < 8:  # untouched by the user
                        nd["restoring"] = True
                        self.win_anim = {"hwnd": nd["hwnd"], "a": (px, py), "b": nd["orig"], "i": 0, "n": 14}
                        return
                self.nudge = None

        def restore_windows_now(self):
            nd = self.nudge
            if nd and user32.IsWindow(nd["hwnd"]):
                px, py = raw_pos(nd["hwnd"])
                if abs(px - nd["cur"][0]) < 8 and abs(py - nd["cur"][1]) < 8 or nd.get("restoring"):
                    move_window(nd["hwnd"], *nd["orig"])
            self.nudge = self.win_anim = None

        # ---- ball play
        def start_play(self):
            side = random.choice((-1, 1))
            bx = min(max(self.x + side * random.randint(250, 450), WA_L + 60), WA_R - 60)
            self.ball.show(bx)
            self.play_hits, self.play_t0, self.bat_t = random.randint(4, 7), time.time(), 0
            self.go("play")

        def st_play(self, now):
            ball = self.ball
            if self.bat_t > 0:
                self.bat_t -= 1
                return
            if now - self.play_t0 > 40 or self.play_hits <= 0:
                self.say("Mine now.", 2.5)
                self.ball_hide_at = now + 4
                self.go("sit", 3)
                return
            dx = ball.x - self.x
            self.face = 1 if dx > 0 else -1
            if abs(dx) < 85:
                if ball.resting:
                    ball.kick(self.face * random.uniform(9, 13))
                    self.play_hits -= 1
                    self.bat_t = 10
            else:
                self.x += self.face * 5

        # ---- feeding / petting / input
        def give_treat(self):
            self.hunger = max(0.0, self.hunger - 60)
            self.affection = min(100.0, self.affection + 5)
            self.say("Nom nom nom... ♥", 3)
            self.go("eat", 3)

        def on_press(self, e):
            if "close" in canvas.gettags("current"):  # the hover x button
                self.press = None
                self.start_goodbye()
                return
            self.press = (e.x_root, e.y_root)
            self.dragging = False

        def on_motion(self, e):
            if self.press and (self.dragging or abs(e.x_root - self.press[0]) + abs(e.y_root - self.press[1]) > 6):
                self.dragging = True
                self.ground()
                self.go("drag")
                self.x, self.fy = e.x_root, e.y_root + CH * 0.45
                self.vx = self.vy = 0

        def on_release(self, e):
            if self.press is None:
                return
            if self.dragging:
                self.land_line = "Hey! Warn a cat first."
                self.go("pounce")
            else:
                self.pet()
            self.press, self.dragging = None, False

        def pet(self):
            if self.state == "ignore" and (self.ign_clicks == 0 or self.affection < 25 and self.ign_clicks < 2):
                self.ign_clicks += 1
                self.say(random.choice(GRUMPY_PET), 2.2)
                self.affection = min(100.0, self.affection + 1)
                return
            if self.affection < 25 and random.random() < 0.5:
                self.say(random.choice(GRUMPY_PET), 2.2)
                self.affection = min(100.0, self.affection + 2)
                return
            self.pets += 1
            self.affection = min(100.0, self.affection + 3)
            if self.state in ("sleep", "walk", "chase", "crouch", "ignore", "stare", "groom", "play"):
                self.idle_sleep = False
                self.go("sit", 3)
            self.happy_until = time.time() + 2.5
            self.say(random.choice(PET_LINES), 2.2)
            for _ in range(4):
                self.fx.append([self.x + random.randint(-30, 30), self.fy - CH, "♥", 1.0, "#ff5577"])

        # ---- states
        def st_enter(self, now):
            self.face = 1
            self.x += 5
            if self.x >= WA_L + CW // 2:
                self.go("ignore", 18) if self.sulky else self.go("sit", 4)
                self.ign_clicks = 0

        def st_sit(self, now):
            if self.blink > 0:
                self.blink -= 1
            elif random.random() < 0.012:
                self.blink = 4
            if self.bubble and now < self.bubble[1]:
                return
            if now - self.t0 < self.dur:
                return
            hour = datetime.datetime.now().hour
            if hour in (2, 3) and not self.said_3am and not self.perch:
                self.said_3am = True
                self.say("It's 3 AM. Zoomies o'clock.", 3)
                self.zoom = 4
                self.walk_to(self.random_x(), 8.0)
                return
            if self.hunger > 70 and now - self.last_hunger_msg > 90:
                self.last_hunger_msg = now
                return self.do("hungry")
            if now > self.next_fact:
                self.next_fact = now + (random.uniform(25, 45) if SPOOKY else random.uniform(35, 70))
                self.say(random.choice(FACTS))
                self.go("sit", 0)
                return
            self.choose_next()

        def st_walk(self, now):
            dx = self.tx - self.x
            if abs(dx) <= self.speed:
                self.x = self.tx
                if self.zoom > 0:
                    self.zoom -= 1
                    self.tx = self.random_x()
                    return
                after, self.after_walk = self.after_walk, None
                if after == "idle_sleep":
                    cx, _ = self.cursor()
                    self.face = 1 if cx > self.x else -1
                    self.idle_sleep = True
                    self.go("sleep", 1e9)
                elif after == "peek":
                    self.face = 1 if self.x >= self.maxx - 1 else -1
                    self.say("...it's a long way down.", 3)
                    self.go("peek", 3.5)
                else:
                    self.go("sit", random.uniform(2, 6))
                return
            self.face = 1 if dx > 0 else -1
            self.x += self.face * self.speed

        def st_sleep(self, now):
            if self.idle_sleep:
                if idle_seconds() < 4:
                    self.idle_sleep = False
                    self.say("Oh! You're back. ♥", 3)
                    self.happy_until = now + 3
                    self.go("sit", 2)
                    return
            elif now - self.t0 > self.dur:
                self.say("*yawn* ...stretch.", 2.5)
                self.go("stretch", 2.8)
                return
            if random.random() < 0.02:
                self.fx.append([self.x + self.face * 40, self.fy - CH * 0.6, "z", 1.4, "#8899cc"])

        def timed_end(self, now):
            s = self.state
            if s == "swat":
                self.do_nudge()
                self.go("sit", 3)
            elif s in ("knead", "loaf") and random.random() < 0.4:
                self.last_nap = now
                self.go("sleep", random.uniform(12, 25))
            elif s == "ignore":
                self.say("Fine. I forgive you.", 2.5) if random.random() < 0.3 else None
                self.go("sit", 2)
            else:
                self.go("sit", random.uniform(1, 3))

        def st_timed(self, now):
            if self.state == "knead":
                if random.random() < 0.03:
                    self.fx.append([self.x + random.randint(-25, 25), self.fy - CH * 0.8, "♥", 1.0, "#ff5577"])
            if now - self.t0 > self.dur:
                self.timed_end(now)

        st_groom = st_stretch = st_knead = st_loaf = st_slowblink = st_ignore = st_peek = st_swat = st_eat = st_timed

        def st_stare(self, now):
            cx, _ = self.cursor()
            self.face = 1 if cx > self.x else -1
            if now - self.t0 > self.dur:
                self.go("chase")

        def st_chase(self, now):
            cx, _ = self.cursor()
            dx = cx - self.x
            self.face = 1 if dx > 0 else -1
            if now - self.t0 > 7:
                self.go("sit", 2)
            elif abs(dx) < 120:
                self.go("crouch", 0.9)
            else:
                self.x += self.face * 6.5

        def st_crouch(self, now):
            cx, _ = self.cursor()
            self.face = 1 if cx > self.x else -1
            if now - self.t0 > self.dur:
                self.vx = max(-9, min(9, (cx - self.x) / 22))
                self.vy = -10
                self.land_line = random.choice(PROUD_LINES) if random.random() < 0.5 else None
                self.go("pounce")

        def st_pounce(self, now):
            self.x += self.vx
            self.vy += 0.9
            self.fy += self.vy
            if self.fy >= self.floor and self.vy > 0:
                self.fy, self.vy, self.vx = self.floor, 0, 0
                self.happy_until = now + 2.5
                if self.land_line:
                    self.say(self.land_line, 2.5)
                    self.land_line = None
                self.go("sit", random.uniform(2, 4))

        def st_jump_to(self, now):
            jt = self.jt
            self.x += self.vx
            self.vy += 0.9
            self.fy += self.vy
            if self.vy > 0 and self.fy >= jt["ty"]:
                self.fy, self.x, self.vy, self.vx = jt["ty"], jt["tx"], 0, 0
                self.perch = jt["perch"]
                if self.perch:
                    l, t, rr, _ = ext_rect(self.perch)
                    self.floor, self.minx, self.maxx = t, max(l, WA_L) + CW // 2, min(rr, WA_R) - CW // 2
                    if random.random() < 0.4:
                        self.say("Hello from up here.", 2.5)
                else:
                    self.ground()
                self.go("sit", 1.5)

        def st_drag(self, now):
            pass

        def st_goodbye(self, now):
            if self.bubble and now < self.bubble[1]:
                return
            self.x += self.face * 7
            if self.x < WA_L - CW or self.x > WA_R + CW:
                quit_pet()

        def start_goodbye(self):
            self.restore_windows_now()
            self.ball.hide()
            self.ground()
            self.say(random.choice(BYES), 3)
            self.fy = WA_B
            self.vx = self.vy = 0
            self.face = -1 if self.x < (WA_L + WA_R) / 2 else 1
            self.go("goodbye")

        # ---- rendering
        def gait(self, kind):
            """Leg frame driven by distance travelled, so paws plant instead of sliding."""
            amp = RUN_AMP if kind == "run" else WALK_AMP
            foot_px = 2 * amp * SCALE  # how far a paw swings in one half-stride
            return kind, int(self.travel / (foot_px / 4)) % 8, "open"

        def frame_key(self, now):
            s, n = self.state, self.n
            eye = "happy" if now < self.happy_until else ("blink" if self.blink > 0 else "open")
            if s in ("enter", "chase"):
                return self.gait("run")
            if s == "walk":
                return self.gait("run" if self.speed > 4 else "walk")
            if s == "goodbye":
                if self.bubble and now < self.bubble[1]:
                    return "sit", (n // 5) % 12, "happy"
                return self.gait("run")
            if s == "crouch":
                return "crouch", (n // 3) % 2, "open"
            if s in ("pounce", "jump_to"):
                return "jump", 0, "open"
            if s == "drag":
                return "hang", 0, "open"
            if s == "sleep":
                return "sleep", int(now * 0.7) % 2, "closed"
            if s == "groom":
                return "groom", (n // 8) % 2, "closed"
            if s == "stretch" or s == "eat":
                return "bow", 0, "happy" if s == "eat" else "closed"
            if s == "peek":
                return "bow", 0, "open"
            if s == "swat":
                return "swat", (n // 6) % 2, "open"
            if s == "knead":
                return "loaf", (n // 10) % 2, "happy"
            if s == "loaf":
                return "loaf", 2, "blink" if self.blink > 0 else "half"
            if s == "stare":
                return "front", (n // 3) % 12, "wide"
            if s == "slowblink":
                p = (now - self.t0) / self.dur
                return "front", (n // 5) % 12, "open" if p < 0.25 else "half" if p < 0.4 else "closed" if p < 0.7 else "half" if p < 0.85 else "open"
            if s == "ignore":
                return "back", (n // 6) % 12, "open"
            if s == "play":
                return ("swat", 1, "open") if self.bat_t > 0 else self.gait("run")
            return "sit", (n // 5) % 12, eye

        def draw_bubble(self, cx, base):
            text, _ = self.bubble
            c = canvas
            fill, line, ink = ("#2a1a38", "#b074ff", "#ffd9a0") if SPOOKY else ("#fffaf0", "#4a2410", "#3a1f0d")
            t = c.create_text(0, 0, text=text, font=font, width=WRAP, anchor="nw", fill=ink, tags="bub")
            x0, y0, x1, y1 = c.bbox(t)
            pad = 10
            bw, bh = x1 - x0 + 2 * pad, y1 - y0 + 2 * pad
            bx = min(max(cx - bw / 2, 4), WIN_W - bw - 4)
            by = max(base - CH - bh + 6, 2)
            c.coords(t, bx + pad, by + pad)
            rr, xa, ya, xb, yb = 12, bx, by, bx + bw, by + bh
            pts = [xa + rr, ya, xb - rr, ya, xb, ya, xb, ya + rr, xb, yb - rr, xb, yb, xb - rr, yb,
                   xa + rr, yb, xa, yb, xa, yb - rr, xa, ya + rr, xa, ya]
            box = c.create_polygon(pts, smooth=True, fill=fill, outline=line, width=2, tags="bub")
            tx = min(max(cx + 12 * self.face, bx + 18), bx + bw - 18)
            tail = c.create_polygon(tx - 7, yb - 1, tx + 7, yb - 1, tx, yb + 11, fill=fill, outline=line, width=2, tags="bub")
            seam = c.create_line(tx - 6, yb, tx + 6, yb, fill=fill, width=3, tags="bub")
            for item in (box, tail, seam, t):
                c.tag_raise(item)

        def draw_close(self, now, cx, base):
            """While the mouse is over her, show a small x near her head; clicking it says goodbye."""
            mx, my = self.cursor()
            if (self.x - CW / 2 - 12 <= mx <= self.x + CW / 2 + 12 and self.fy - CH - 24 <= my <= self.fy + 4
                    and self.state not in ("goodbye", "drag")):
                self.hover_until = now + 1.2
            canvas.delete("close")
            if now >= self.hover_until or self.state == "goodbye":
                return
            r = int(9 * k)
            bx = min(cx + CW * 0.36, WIN_W - r - 3)
            by = max(base - CH * 0.92, r + 3)
            canvas.create_oval(bx - r, by - r, bx + r, by + r, fill="#fffaf0", outline="#3a1f0d", width=2, tags="close")
            d = r * 0.42
            canvas.create_line(bx - d, by - d, bx + d, by + d, fill="#3a1f0d", width=2, tags="close")
            canvas.create_line(bx - d, by + d, bx + d, by - d, fill="#3a1f0d", width=2, tags="close")

        def render(self, now):
            self.n += 1
            free = self.state in ("enter", "goodbye")
            if not free:
                self.clamp_x()
            self.travel += abs(self.x - self.last_x)
            self.last_x = self.x
            kind, i, eye = self.frame_key(now)
            canvas.itemconfig(cat_item, image=photo(kind, i, eye, self.face))
            wx = int(self.x - WIN_W / 2)
            if not free:
                wx = min(max(wx, WA_L), WA_R - WIN_W)
            wy = max(int(self.fy - WIN_H), WA_T)
            base = self.fy - wy
            cx = self.x - wx
            canvas.coords(cat_item, cx, base)
            root.geometry(f"{WIN_W}x{WIN_H}+{wx}+{wy}")
            self.draw_close(now, cx, base)
            canvas.delete("bub")
            canvas.delete("fx")
            if self.bubble:
                if now < self.bubble[1]:
                    self.draw_bubble(cx, base)
                else:
                    self.bubble = None
            for f in self.fx[:]:
                f[1] -= 1.2
                f[3] -= 0.025
                if f[3] <= 0:
                    self.fx.remove(f)
                    continue
                canvas.create_text(f[0] - wx, f[1] - wy, text=f[2], font=big, fill=f[4], tags="fx")

        # ---- demo mode (cycles through every behaviour, for testing)
        DEMO = ["walk", "run", "chase", "groom", "stretch", "knead", "loaf", "slowblink", "ignore", "ball",
                "perch", "swat", "peek", "descend", "zoomies", "hop", "nap", "treat", "fact", "hungry"]

        def demo_step(self, now):
            if now < self.demo_t or self.state in ("jump_to", "enter", "goodbye"):
                return
            name = self.DEMO[self.demo_i % len(self.DEMO)]
            if name in ("swat", "peek", "descend") and not self.perch:
                name = "perch"
            self.demo_i += 1
            self.demo_t = now + (7 if name in ("perch", "swat", "ball") else 4.5)
            log(f"demo: {name} (state before: {self.state}, perch={bool(self.perch)})")
            self.bubble = None
            self.do(name)
            if name == "swat":
                self.state, self.dur = "swat", 1.5

        def tick(self):
            if self.dead:
                return
            now = time.time()
            try:
                if STOP_FILE.exists() and self.state != "goodbye":
                    self.start_goodbye()
                if self.n % 15 == 0 and CMD_FILE.exists():
                    try:
                        cmd = CMD_FILE.read_text().strip()
                        CMD_FILE.unlink()
                    except OSError:
                        cmd = ""
                    if cmd == "feed":
                        self.give_treat()
                if self.n % 60 == 0:
                    self.affection = max(0.0, self.affection - 2 / 3600 * 2)
                    self.hunger = min(100.0, self.hunger + 12 / 3600 * 2)
                    if idle_seconds() < 10:
                        self.idle_done = False
                    if now - self.last_save > 30:
                        self.last_save = now
                        self.save()
                    if now % 4 < 2:
                        root.attributes("-topmost", True)
                if demo:
                    self.demo_step(now)
                self.track_perch()
                getattr(self, "st_" + self.state)(now)
                if self.dead:
                    return
                self.tick_window_stuff(now)
                ball = self.ball
                if ball.visible:
                    ball.step()
                    ball.place()
                    if self.state != "play" and not self.ball_hide_at:
                        self.ball_hide_at = now + 4  # play was interrupted: put the ball away
                    if self.ball_hide_at and now > self.ball_hide_at and self.state != "play":
                        ball.hide()
                        self.ball_hide_at = 0.0
                self.render(now)
            except Exception:
                self.errors += 1
                log("tick error: " + traceback.format_exc())
                if self.errors > 5:
                    self.errors = 0
                    self.ground()
                    self.fy = WA_B
                    self.go("sit", 2)
            root.after(33, self.tick)

    nini = Nini()
    canvas.bind("<ButtonPress-1>", nini.on_press)
    canvas.tag_bind("close", "<Enter>", lambda e: canvas.config(cursor="hand2"))
    canvas.tag_bind("close", "<Leave>", lambda e: canvas.config(cursor=""))
    canvas.bind("<B1-Motion>", nini.on_motion)
    canvas.bind("<ButtonRelease-1>", nini.on_release)

    def status_line():
        nini.say(f"Mood: {nini.mood()}. Affection {int(nini.affection)}/100, hunger {int(nini.hunger)}/100.", 5)

    menu = tk.Menu(root, tearoff=0)
    menu.add_command(label="Tell me something spooky", command=lambda: nini.do("fact"))
    menu.add_command(label="Give a treat", command=nini.give_treat)
    menu.add_command(label="Chase my mouse", command=lambda: nini.do("chase"))
    menu.add_command(label="Play with the yarn ball", command=lambda: nini.do("ball"))
    menu.add_command(label="Climb on a window", command=lambda: nini.do("perch"))
    menu.add_command(label="Take a nap", command=lambda: nini.do("nap"))
    menu.add_command(label="How's Nini feeling?", command=status_line)
    menu.add_separator()
    menu.add_command(label="Say goodbye", command=lambda: nini.start_goodbye())
    canvas.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))

    def quit_pet():
        if nini.dead:
            return
        nini.dead = True
        log("quit")
        nini.restore_windows_now()
        nini.save()
        for f in (PID_FILE, STOP_FILE):
            try:
                f.unlink()
            except OSError:
                pass
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", quit_pet)
    STATE_DIR.mkdir(exist_ok=True)
    try:
        STOP_FILE.unlink()
    except OSError:
        pass
    PID_FILE.write_text(str(os.getpid()))
    nini.tick()
    root.mainloop()


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def pid_alive(pid):
    h = kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
    if not h:
        return False
    code = ctypes.c_ulong()
    kernel32.GetExitCodeProcess(h, ctypes.byref(code))
    kernel32.CloseHandle(h)
    return code.value == 259  # STILL_ACTIVE


def running_pid():
    try:
        pid = int(PID_FILE.read_text())
    except (OSError, ValueError):
        return None
    return pid if pid_alive(pid) else None


def main():
    args = sys.argv[1:]
    if getattr(sys, "frozen", False) and not args:  # the downloaded Nini.exe was double-clicked
        if running_pid():
            user32.MessageBoxW(None, "Nini is already on your screen!\nHover over her and click the x to close her.", "Nini", 0x40)
            return
        run_pet()
        return
    arg = args[0].lower() if args else "help"
    if arg == "--run":
        run_pet(demo="--demo" in args)
    elif arg in ("wake", "start"):
        if running_pid():
            print("Nini is already awake and watching you.")
            return
        STATE_DIR.mkdir(exist_ok=True)
        try:
            STOP_FILE.unlink()
        except OSError:
            pass
        if getattr(sys, "frozen", False):
            cmd = [sys.executable, "--run"]
        else:
            py = Path(sys.executable).with_name("pythonw.exe")
            cmd = [str(py if py.exists() else sys.executable), str(Path(__file__).resolve()), "--run"]
        subprocess.Popen(cmd,
                         creationflags=0x00000008 | 0x08000000, close_fds=True)  # DETACHED | NO_WINDOW
        print("Nini wakes up and stretches... meow!")
    elif arg in ("sleep", "stop"):
        pid = running_pid()
        if not pid:
            print("Nini is already asleep.")
            return
        STATE_DIR.mkdir(exist_ok=True)
        STOP_FILE.write_text("bye")
        for _ in range(100):
            if not pid_alive(pid):
                print("Nini curls up in the shadows. Goodnight.")
                return
            time.sleep(0.1)
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
        print("Nini was grumpy and had to be carried off.")
    elif arg == "status":
        pet = load_json(PET_FILE, {"affection": 60.0, "hunger": 25.0})
        print("Nini is prowling your screen." if running_pid() else "Nini is asleep.")
        print(f"Affection {int(pet['affection'])}/100, hunger {int(pet['hunger'])}/100.")
    elif arg == "feed":
        if not running_pid():
            print("Nini is asleep. Wake her first: nini wake")
            return
        STATE_DIR.mkdir(exist_ok=True)
        CMD_FILE.write_text("feed")
        print("You hold out a treat. Nini's ears perk up.")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
