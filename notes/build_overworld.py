"""Build the overworld-plan artifacts: overlay PNG, schematic PNG, markdown table.

The playable-Eriador window is mapped to a 15x9 square grid (stride ~3 hexes),
origin (0,0) at the window's geographic centre = the Bree crossroads.
Coordinates: x in [-7..+7] (west->east), y in [-4..+4] (north->south, y-down).
"""
import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = "/Users/jfarber/dev/the_lonelands"
NOTES = os.path.join(REPO, "notes")
os.makedirs(NOTES, exist_ok=True)

# --- the window box in reference-jpeg pixels -------------------------------
X0, X1 = 700, 1920          # west edge (Blue Mts) -> east edge (Misty Mts)
Y0, Y1 = 330, 1070          # north (North Downs) -> south (Tharbad/Enedwaith)
COLS, ROWS = 15, 9          # x in -7..+7, y in -4..+4
CW = (X1 - X0) / COLS       # cell width  px  (~81)
CH = (Y1 - Y0) / ROWS       # cell height px  (~82)
CX0, CY0 = 7, 4             # grid index of coord (0,0)

def cell_of(px, py):
    c = min(COLS - 1, max(0, round((px - X0) / CW - 0.5)))
    r = min(ROWS - 1, max(0, round((py - Y0) / CH - 0.5)))
    return (c - CX0, r - CY0)

def cell_center_px(x, y):
    c, r = x + CX0, y + CY0
    return (X0 + (c + 0.5) * CW, Y0 + (r + 0.5) * CH)

# --- band palette (from the reference legend colours) ----------------------
BANDS = {
    "Free":     "#7ba05b",   # Free Lands  (green)
    "Wild":     "#d9b866",   # Wild Lands  (tan)
    "Dark":     "#c8823c",   # Dark Lands  (orange)
    "Perilous": "#9c3b2e",   # Perilous Area (deep red)
    "Impass":   "#5a6b74",   # Impassable (grey-blue: sea/mountain)
}
ROLE_MARK = {"Town": "T", "Landmark": "L", "Wilderness": "W",
             "Gateway": "G", "Impassable": "X"}

# --- the authored anchors --------------------------------------------------
# name, px, py, role, band, deeps(0/levels), note
ANCHORS = [
    ("Bree",              1300, 700, "Town",     "Free", 0, "The hub, at the meeting of the roads; a Ranger is met here."),
    ("Michel Delving",    1010, 710, "Town",     "Free", 0, "Chief town of the Shire; the Mathom-house."),
    ("Hobbiton",          1100, 635, "Town",     "Free", 0, "Hobbit hamlet; the Hill and Bag End."),
    ("Brandywine Bridge", 1180, 640, "Landmark", "Free", 0, "Stone bridge; the Shire's eastern gate onto the Road."),
    ("Grey Havens",       745,  660, "Town",     "Free", 0, "Mithlond; elven port. Western gateway (ships west, later)."),
    ("White Towers",      855,  690, "Landmark", "Free", 0, "Elostirion; the palantir that looks only to the Sea."),
    ("Tower Hills",       870,  765, "Wilderness","Free",0, "Emyn Beraid; green marches west of the Far Downs."),
    ("Far Downs",         945,  740, "Wilderness","Free",0, "The Shire's western downs."),
    ("Annuminas",         1045, 545, "Landmark", "Wild", 3, "Ruined royal city on Lake Nenuial; deeps into the drowned halls."),
    ("Fornost",           1245, 515, "Landmark", "Wild", 2, "Norbury of the Kings; ruined Arnor capital, wight-haunted deeps."),
    ("North Downs",       1365, 390, "Landmark", "Wild", 0, "Rolling high downs; the road to the ruined north."),
    ("Chetwood",          1320, 640, "Wilderness","Wild",0, "Wooded country north of Bree."),
    ("Midgewater",        1405, 635, "Landmark", "Perilous", 0, "Midgewater Marshes; biting fen, easy to lose the Road."),
    ("Weather Hills",     1445, 570, "Wilderness","Wild",0, "The ridge-line running north from Weathertop."),
    ("Weathertop",        1500, 665, "Landmark", "Wild", 3, "Amon Sul; ruined watchtower, deeps to the watch-chamber."),
    ("Barrow-downs",      1225, 730, "Landmark", "Perilous", 4, "Tyrn Gorthad; the barrow-wights and their deeps."),
    ("Old Forest",        1165, 745, "Landmark", "Perilous", 0, "Ancient wood; the trees are awake and ill-disposed."),
    ("Sarn Ford",         1230, 820, "Landmark", "Wild", 0, "The Brandywine ford; a Ranger watch-post on the south road."),
    ("South Downs",       1340, 785, "Wilderness","Wild",0, "Low downs south of the Great Road."),
    ("Cardolan",          1400, 870, "Wilderness","Wild",0, "Emptied old realm; barrows and broken keeps."),
    ("Tharbad",           1360, 1020,"Landmark", "Wild", 2, "Ruined river-city on the Greyflood; southern gateway. Silted deeps."),
    ("Last Bridge",       1625, 630, "Landmark", "Wild", 0, "The Mitheithel bridge on the East Road; the Road's last sure crossing."),
    ("Trollshaws",        1710, 620, "Landmark", "Perilous", 1, "Troll-country east of the Hoarwell; stone-trolls and their holes."),
    ("Fords of Bruinen",  1850, 645, "Gateway",  "Wild", 0, "The Bruinen crossing; the guarded threshold of Rivendell."),
    ("Rivendell",         1805, 690, "Gateway",  "Free", 0, "Imladris; the Last Homely House. Eastern gateway (beyond, later)."),
    ("Ettenmoors",        1690, 410, "Landmark", "Perilous", 0, "Troll-fells; north-east gateway toward Angmar."),
    ("Mt Gram",           1650, 350, "Landmark", "Dark", 2, "Orc-hold of the northern hills; deeps into the goblin-warren."),
    ("Redhorn Pass",      1775, 885, "Gateway",  "Dark", 0, "Caradhras pass over the Misty Mountains (beyond, later)."),
    ("Moria West-gate",   1730, 960, "Gateway",  "Perilous", 5, "Hollin gate of Khazad-dum; the Watcher and the long dark."),
    ("Ost-in-Edhil",      1620, 960, "Landmark", "Wild", 2, "Ruined Eregion city of the Elven-smiths; cellars and forges."),
]

# resolve to cells, nudging off collisions (deterministic order)
placed = {}
cells = {}
for name, px, py, role, band, deeps, note in ANCHORS:
    x, y = cell_of(px, py)
    while (x, y) in placed:              # bump west, then north, to free a cell
        if (x - 1, y) not in placed and x - 1 >= -7: x -= 1
        elif (x, y - 1) not in placed and y - 1 >= -4: y -= 1
        else: x -= 1
    placed[(x, y)] = name
    cells[(x, y)] = dict(name=name, role=role, band=band, deeps=deeps, note=note)

# --- default band/role for every un-authored cell --------------------------
def default_cell(x, y):
    # impassable frame: far-west sea, far-east Misty Mountains wall
    if x <= -7:                      return ("Impassable", "Impass", "The Great Sea / Gulf of Lune.")
    if x >= 7 and y != 0:            return ("Impassable", "Impass", "The Misty Mountains wall.")
    if (x, y) in [(6, 4)]:           return ("Impassable", "Impass", "Southern spur of the Misty Mountains.")
    if x <= -6 and y >= 2:           return ("Impassable", "Impass", "The Gulf of Lune.")
    # bands by geography
    if -6 <= x <= 0 and 0 <= y <= 1: band = "Free"      # Shire / Arthedain green
    elif y <= -3 and x >= 4:         band = "Dark"       # Angmar / Rhudaur NE
    elif x >= 5 and y <= 0:          band = "Dark"       # Rhudaur east
    else:                            band = "Wild"
    return ("Wilderness", band, "Open country; encounters drawn from the %s table." %
            {"Free": "Free-Lands", "Wild": "Wild-Lands", "Dark": "Dark-Lands"}[band])

grid = {}
for r in range(ROWS):
    for c in range(COLS):
        x, y = c - CX0, r - CY0
        if (x, y) in cells:
            grid[(x, y)] = cells[(x, y)]
        else:
            role, band, note = default_cell(x, y)
            grid[(x, y)] = dict(name="", role=role, band=band, deeps=0, note=note)

# --- roads --------------------------------------------------------------
# Cell-paths that follow the real map's line, not straight axes. The Great East
# Road bows NORTH after Weathertop (climbing to Last Bridge / Trollshaws) then
# hooks back SOUTH across the Bruinen to Rivendell -- exactly its shape on the
# journey map. Greenway runs Fornost -> Bree -> Sarn Ford and bends SE to
# Tharbad. Stored as ordered cell-paths; rendered as smooth bowed splines.
EAST_ROAD = [(0, 0), (1, 0), (2, 0), (3, 0), (3, -1), (4, -1),
             (5, -1), (6, -1), (7, -1), (7, 0), (6, 0)]   # Bree -> Rivendell
GREENWAY  = [(0, -2), (0, -1), (0, 0), (0, 1), (0, 2),
             (1, 3), (1, 4)]                              # Fornost -> Tharbad
SHIRE_ROAD = [(-4, 0), (-3, -1), (-2, -1), (-1, 0), (0, 0)]  # Michel Delving -> Bree
ROAD_CELLS = set(EAST_ROAD) | set(GREENWAY) | set(SHIRE_ROAD)

# --- smooth, gently-meandering road geometry (shared by both renders) -------
import numpy as np

def _bow(cells, amp=0.24):
    """Insert a perpendicular-offset midpoint between each pair of cells so the
    curve bows instead of running straight; sign alternates for an S-weave."""
    pts = [np.array(c, float) for c in cells]
    aug = [pts[0]]
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        d = b - a
        n = np.array([-d[1], d[0]])
        ln = np.hypot(*n)
        if ln:
            n = n / ln
        aug.append((a + b) / 2 + n * amp * (1 if i % 2 == 0 else -1))
        aug.append(b)
    return aug

def _catmull(pts, samples=18):
    """Catmull-Rom spline through pts (list of 2-vectors) -> smooth polyline."""
    if len(pts) < 3:
        return np.array(pts)
    P = np.vstack([pts[0], *pts, pts[-1]])
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for t in np.linspace(0, 1, samples, endpoint=False):
            t2, t3 = t * t, t * t * t
            out.append(0.5 * (2 * p1 + (-p0 + p2) * t
                              + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(P[-2])
    return np.array(out)

def road_curve(cells):
    """Grid-space smooth meandering curve (Nx2 array of fractional x,y coords)."""
    return _catmull(_bow(cells))

def grid_to_px(gx, gy):
    return (X0 + (gx + CX0 + 0.5) * CW, Y0 + (gy + CY0 + 0.5) * CH)

# ===========================================================================
# 1) OVERLAY on the reference jpeg
# ===========================================================================
base = Image.open(os.path.join(REPO, "references/eriador-journey-map.jpeg")).convert("RGBA")
ov = Image.new("RGBA", base.size, (0, 0, 0, 0))
d = ImageDraw.Draw(ov)

def font(sz):
    for p in ["/System/Library/Fonts/Supplemental/Arial Bold.ttf",
              "/System/Library/Fonts/Helvetica.ttc"]:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, sz)
            except Exception: pass
    return ImageFont.load_default()

f_coord = font(14)
f_name = font(15)

def hexcol(h, a):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)

# band tint + grid
for (x, y), cell in grid.items():
    c, r = x + CX0, y + CY0
    x0p, y0p = X0 + c * CW, Y0 + r * CH
    x1p, y1p = x0p + CW, y0p + CH
    d.rectangle([x0p, y0p, x1p, y1p], fill=hexcol(BANDS[cell["band"]], 70),
                outline=(30, 20, 10, 200), width=1)
    d.text((x0p + 3, y0p + 2), f"{x:+d},{y:+d}", font=f_coord, fill=(20, 15, 5, 255))

# roads -- smooth, meandering curves
def road_line(cellseq):
    pts = [grid_to_px(gx, gy) for gx, gy in road_curve(cellseq)]
    d.line(pts, fill=(120, 40, 20, 235), width=7, joint="curve")
    d.line(pts, fill=(232, 201, 143, 210), width=2, joint="curve")
road_line(EAST_ROAD)
road_line(GREENWAY)
road_line(SHIRE_ROAD)

# anchor dots + names
for (x, y), cell in cells.items():
    cx, cy = cell_center_px(x, y)
    rr = 7
    d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr],
              fill=(255, 250, 235, 255), outline=(0, 0, 0, 255), width=2)
    d.text((cx + 10, cy - 8), cell["name"], font=f_name, fill=(0, 0, 0, 255))
    d.text((cx + 9, cy - 9), cell["name"], font=f_name, fill=(255, 244, 214, 255))

out = Image.alpha_composite(base, ov).convert("RGB")
overlay_path = os.path.join(NOTES, "eriador-grid-overlay.png")
out.save(overlay_path, quality=90)
print("wrote", overlay_path)

# ===========================================================================
# 2) SCHEMATIC (fresh render, no jpeg)
# ===========================================================================
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrow

fig, ax = plt.subplots(figsize=(15, 9.5), dpi=130)
for (x, y), cell in grid.items():
    # screen: x right, y down -> invert y for plotting
    px, py = x, -y
    ax.add_patch(Rectangle((px - 0.5, py - 0.5), 1, 1,
                 facecolor=BANDS[cell["band"]], edgecolor="#2b1d10", linewidth=1.0,
                 alpha=0.92 if cell["name"] else 0.65))
    if cell["role"] == "Impassable":
        ax.text(px, py, "▲" if x >= 6 or y <= -3 else "≈",
                ha="center", va="center", fontsize=16, color="#dfe7ea")
        continue
    if cell["name"]:
        ax.text(px, py + 0.10, cell["name"], ha="center", va="center",
                fontsize=8.2, fontweight="bold", color="#1a1206")
        tag = ROLE_MARK[cell["role"]]
        if cell["deeps"]:
            tag += f"  ▼{cell['deeps']}"
        ax.text(px, py - 0.24, tag, ha="center", va="center",
                fontsize=7, color="#1a1206")
    ax.text(px - 0.44, py - 0.40, f"{x:+d},{y:+d}", ha="left", va="center",
            fontsize=5.2, color="#3b2b18")

# roads -- smooth, meandering curves
def draw_road(cellseq):
    curve = road_curve(cellseq)
    xs, ys = curve[:, 0], -curve[:, 1]
    ax.plot(xs, ys, color="#5b2310", linewidth=3.4, solid_capstyle="round", zorder=5)
    ax.plot(xs, ys, color="#e8c98f", linewidth=1.0, linestyle=(0, (2, 2)), zorder=6)
draw_road(EAST_ROAD); draw_road(GREENWAY); draw_road(SHIRE_ROAD)

ax.set_xlim(-7.6, 7.6); ax.set_ylim(-4.6, 4.6)
ax.set_aspect("equal"); ax.axis("off")
ax.set_title("The Lonelands — Overworld Grid (playable Eriador, stride ≈3 hexes)\n"
             "origin (0,0) = the Bree crossroads · roads follow the journey-map line",
             fontsize=13, fontweight="bold", color="#2b1d10", pad=14)

# legend
from matplotlib.patches import Patch
leg = [Patch(facecolor=BANDS[b], edgecolor="#2b1d10", label=l) for b, l in
       [("Free", "Free Lands"), ("Wild", "Wild Lands"), ("Dark", "Dark Lands"),
        ("Perilous", "Perilous Area"), ("Impass", "Impassable (frame)")]]
ax.legend(handles=leg, loc="lower left", fontsize=7.5, framealpha=0.9,
          title="Band", title_fontsize=8, ncol=5, bbox_to_anchor=(0.0, -0.06))
ax.text(7.5, -4.55, "T town  L landmark  W wild  G gateway   ▼N deeps (N levels)",
        ha="right", va="center", fontsize=7, color="#2b1d10")

schem_path = os.path.join(NOTES, "eriador-grid-schematic.png")
fig.savefig(schem_path, bbox_inches="tight", facecolor="#efe7d4")
print("wrote", schem_path)

# ===========================================================================
# 3) markdown table rows (emitted for the .md writer)
# ===========================================================================
rows = []
for (x, y) in sorted(cells.keys(), key=lambda k: (k[1], k[0])):
    c = cells[(x, y)]
    onroad = "yes" if (x, y) in ROAD_CELLS else "–"
    deeps = f"▼{c['deeps']}" if c["deeps"] else "–"
    rows.append(f"| `{x:+d},{y:+d}` | {c['name']} | {c['role']} | {c['band']} | "
                f"{deeps} | {onroad} | {c['note']} |")
with open(os.path.join(HERE, "table_rows.md"), "w") as fh:
    fh.write("\n".join(rows))
print(f"{len(cells)} anchors placed;", len(ROAD_CELLS), "road cells")
print("IMPASSABLE:", sum(1 for v in grid.values() if v['role'] == 'Impassable'),
      " WILDERNESS:", sum(1 for v in grid.values() if v['role'] == 'Wilderness'))
