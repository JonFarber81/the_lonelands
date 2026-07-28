"""Overworld Map screen tests (issue #63): the *pure* rendering bits of the
atlas — road-seam glyph selection off `ROAD_EDGES` and label placement with its
collision fallback — plus a few whole-buffer sanity checks. No tcod console is
touched; the module builds an in-memory buffer we can assert against."""
from __future__ import annotations

from lonelands import overworld, overworld_map as om


# --- road-seam glyph selection ---------------------------------------------

def test_seam_glyph_maps_edges_to_line_glyphs():
    # A road crossing only E/W reads as a horizontal line; only N/S vertical;
    # both axes as a crossing. No road edges -> no glyph.
    assert om.seam_glyph(frozenset()) == ""
    assert om.seam_glyph(frozenset("e")) == om.ROAD_H
    assert om.seam_glyph(frozenset("w")) == om.ROAD_H
    assert om.seam_glyph(frozenset("ew")) == om.ROAD_H
    assert om.seam_glyph(frozenset("n")) == om.ROAD_V
    assert om.seam_glyph(frozenset("s")) == om.ROAD_V
    assert om.seam_glyph(frozenset("ns")) == om.ROAD_V
    assert om.seam_glyph(frozenset("ne")) == om.ROAD_CROSS
    assert om.seam_glyph(frozenset("nsew")) == om.ROAD_CROSS


def test_seam_glyph_matches_real_road_edges():
    # Bree (0,0) is the crossing of three roads — every axis, so a ┼.
    assert om.seam_glyph(overworld.road_edges((0, 0))) == om.ROAD_CROSS
    # Weathertop (2,0) sits along the East Road's east–west run.
    assert om.seam_glyph(overworld.road_edges((2, 0))) == om.ROAD_H
    # A trackless cell carries no road glyph.
    assert om.seam_glyph(overworld.road_edges((3, -4))) == ""


# --- label placement / collision fallback ----------------------------------

def test_label_placed_on_free_row():
    placed, dropped = om.place_labels(
        [(10, 5, "Bree", overworld.TOWN)], protected=set(), width=40, height=20)
    assert dropped == []
    p, = placed
    assert p.text == "Bree"
    assert p.role == overworld.TOWN          # role is carried through, not re-derived
    # Every cell it lands on is inside bounds and clear of glyphs.
    for i in range(len(p.text)):
        assert 0 <= p.col + i < 40


def test_label_never_clobbers_a_glyph():
    # Fill the label's natural (centered, below) row so it cannot sit there; it
    # must fall back to another candidate and still avoid every protected cell.
    protected = {(c, 6) for c in range(40)}
    placed, dropped = om.place_labels(
        [(10, 5, "Bree", overworld.TOWN)], protected=protected, width=40, height=20)
    p, = placed
    assert p.row != 6
    assert all((p.col + i, p.row) not in protected for i in range(len(p.text)))


def test_label_dropped_when_nowhere_fits():
    # Protect every cell: no run of free cells exists, so the name is dropped
    # (still discoverable via the cursor footer).
    protected = {(c, r) for c in range(40) for r in range(20)}
    placed, dropped = om.place_labels(
        [(10, 5, "Bree", overworld.TOWN)], protected=protected, width=40, height=20)
    assert placed == []
    assert len(dropped) == 1


def test_towns_win_collisions_over_landmarks():
    # A Town and a Landmark contend for the same strip; the Town claims it and
    # the Landmark yields to another spot (or is dropped) — never the reverse.
    town = (10, 5, "Bree", overworld.TOWN)
    mark = (10, 5, "Ruin", overworld.LANDMARK)
    placed, dropped = om.place_labels(
        [mark, town], protected=set(), width=18, height=20)
    by_text = {p.text: p for p in placed}
    assert "Bree" in by_text, "the Town must always be placed"
    if "Ruin" in by_text:
        assert (by_text["Bree"].col, by_text["Bree"].row) != \
            (by_text["Ruin"].col, by_text["Ruin"].row)
    else:
        assert any(d.text == "Ruin" for d in dropped)


# --- whole-buffer sanity ----------------------------------------------------

def test_buffer_marks_the_player_region():
    buf = om.render_map(player_coord=(0, 0), cursor_coord=(0, 0))
    assert buf.width == om.GRID_W
    assert buf.height >= om.GRID_H
    cx, cy = om.cell_center((0, 0))
    assert buf.ch[cy][cx] == om.PLAYER_GLYPH


def test_deeps_cells_get_the_deeps_glyph():
    # Weathertop (2,0) carries 3 deeps -> a ▼ appears somewhere in its block.
    buf = om.render_map(player_coord=(0, 0), cursor_coord=(0, 0))
    ox, oy = om.cell_origin((2, 0))
    block = [buf.ch[oy + r][ox + c]
             for r in range(om.CELL_H) for c in range(om.CELL_W)]
    assert om.DEEPS_GLYPH in block


def test_region_names_are_placed_not_baked_into_cells():
    # Names are laid out for the handler to draw natively (proportional font),
    # not stamped a glyph-per-cell into the buffer. So placements exist, carry a
    # colour by role, and never land on a protected (glyph-bearing) cell.
    buf = om.render_map(player_coord=(0, 0), cursor_coord=(0, 0))
    assert buf.placements, "Region names should be laid out as placements"
    hobbiton = next((p for p in buf.placements if p.text == "Hobbiton"), None)
    assert hobbiton is not None and hobbiton.fg == om.TOWN_NAME_FG
    for p in buf.placements:
        for i in range(len(p.text)):
            assert (p.col + i, p.row) not in buf.protected


def test_describe_off_grid_reads_as_sea_and_mountains():
    sea = om.describe((-7, 3))       # the Gulf of Lune, absent from the grid
    assert sea.off_grid and "Sea" in sea.title
    mtn = om.describe((7, 2))        # the Misty Mountains wall
    assert mtn.off_grid and "Misty" in mtn.title


def test_describe_a_region_carries_name_note_and_deeps():
    d = om.describe((2, 0))          # Weathertop
    assert not d.off_grid
    assert d.title == "Weathertop"
    assert d.deeps == 3
    assert d.note
