"""Hand-author 16x16 side-profile quadrupeds (wolf, warg, boar) that fit the
Kenney/Tiny-Dungeon pixel look: dark outline, 3-4 tone fur ramp, small light
accents. Emits a packed sheet (16px tiles + 1px margin, STEP=17) beside itself."""
import os

from PIL import Image

TILE = 16
STEP = 17

# --- palettes ------------------------------------------------------------
# letter -> RGBA. '.' / ' ' = transparent.
def P(**kw):
    return kw

WOLF = {
    "k": (26, 24, 30, 255),      # outline / nose
    "d": (78, 84, 96, 255),      # dark fur / shadow
    "g": (120, 126, 140, 255),   # mid fur
    "l": (160, 166, 180, 255),   # light fur / belly
    "e": (222, 202, 96, 255),    # eye (amber)
    "t": (225, 227, 233, 255),   # tooth / claw glint
}
WARG = {
    "k": (20, 16, 18, 255),
    "d": (58, 46, 44, 255),      # dark brown-black
    "g": (92, 74, 66, 255),      # brown fur
    "l": (126, 104, 90, 255),    # light brown
    "e": (216, 72, 52, 255),     # red eye
    "t": (232, 228, 214, 255),   # fang
}
BOAR = {
    "k": (28, 22, 20, 255),
    "d": (74, 58, 46, 255),      # dark hide
    "g": (108, 86, 66, 255),     # mid hide
    "l": (140, 116, 92, 255),    # light hide / snout
    "e": (24, 20, 18, 255),      # dark eye
    "t": (236, 232, 220, 255),   # tusk
}

# --- pixel maps (16 rows x 16 cols) --------------------------------------
# Side profile, head to the LEFT, tail to the RIGHT, four legs below.
WOLF_MAP = [
    "................",
    "...k..k.........",   # pricked ears
    "..kdkkdk...kk...",   # ears + head top, tail nub upper-right
    "..kdddddk.kddk..",
    ".kdggggddkdgddk.",   # forehead + raised bushy tail
    ".kdgeggddddgddk.",   # eye
    "kndggggggggggdk.",   # nose at left
    "kndgggggggggggk.",
    ".kdgggggggggggk.",
    ".kdgllllllllgdk.",   # belly (lighter)
    ".kdllllllllllgk.",
    "...kk.kk.kk.kk..",   # four legs
    "...dd.dd.dd.dd..",
    "...dd.dd.dd.dd..",
    "...kk.kk.kk.kk..",   # dark paws
    "................",
]
WARG_MAP = [
    "......k..k......",   # tall pricked ears
    "...k.kdkkdk.....",
    "..kdkddddddk.kk.",   # head + tail nub
    "..kddgggggdkkddk",
    ".kddgggggggggddk",   # raised spiky tail
    ".kdgeggggggggdk.",   # red eye
    "kndgggggggggggk.",   # nose
    "kndggttgggggggk.",   # small bared fangs
    ".kdgggggggggggk.",
    ".kdgllllllllgdk.",
    ".kdllllllllllgk.",
    "...kk.kk.kk.kk..",
    "...dd.dd.dd.dd..",
    "...dd.dd.dd.dd..",
    "...kk.kk.kk.kk..",
    "................",
]
BOAR_MAP = [
    "................",
    "................",
    ".......kkkk.....",   # bristled hump
    "....kk.kddddk...",
    "...kddkddggggk..",
    "..kddgggggggggk.",   # heavy shoulders
    ".kddgggggggggdk.",
    "knddgeggggggggk.",   # eye
    "kltdgggggggggdk.",   # light snout (l) + tusk (t) at left
    "kldgggggggggggk.",
    ".kdglllllllllgk.",
    "...kk.kk.kk.kk..",   # short stout legs
    "...dd.dd.dd.dd..",
    "...dd.dd.dd.dd..",
    "...kk.kk.kk.kk..",
    "................",
]

CREATURES = [("wolf", WOLF, WOLF_MAP), ("warg", WARG, WARG_MAP), ("boar", BOAR, BOAR_MAP)]


def paint(pal, rows):
    img = Image.new("RGBA", (TILE, TILE), (0, 0, 0, 0))
    px = img.load()
    for y, row in enumerate(rows[:TILE]):
        for x, ch in enumerate(row[:TILE]):
            c = pal.get(ch)
            if c:
                px[x, y] = c
    return img


sheet = Image.new("RGBA", (STEP * len(CREATURES) - 1, TILE), (0, 0, 0, 0))
for i, (_, pal, rows) in enumerate(CREATURES):
    sheet.alpha_composite(paint(pal, rows), (i * STEP, 0))
sheet.save(os.path.join(os.path.dirname(os.path.abspath(__file__)), "custom_beasts.png"))
print("wrote custom_beasts.png (tiles: %s)" % ", ".join(n for n, _, _ in CREATURES))
