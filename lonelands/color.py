"""A curated palette. Earthy, desaturated hues in the Brogue tradition, but
pitched *bold and readable* first — atmospheric through hue, legible through a
wide brightness range. See CONTEXT.md "chrome visual language" for how the
luminance tiers, filled bars, rules and stateful colours are meant to be used."""
from __future__ import annotations

# --- UI base ---------------------------------------------------------------
black = (0, 0, 0)
near_black = (10, 10, 14)
# Background for UI chrome (sidebar, Chronicle, popups). A cool dark stone tone
# so the interface reads as worked grey stone, distinct from the black play
# field. Swap this one value to re-theme all panels at once.
panel_bg = (0x27, 0x28, 0x2C)  # dark stone
white = (0xE8, 0xE4, 0xD8)
gray = (0x8A, 0x86, 0x7C)
dark_gray = (0x4A, 0x47, 0x42)
light_gray = (0xB8, 0xB2, 0xA6)

# --- Message log semantics -------------------------------------------------
welcome_text = (0x9A, 0xC7, 0xE0)
health_recovered = (0x6C, 0xC0, 0x6C)
hope_gain = (0xF0, 0xD9, 0x7A)
hope_spend = (0xC8, 0xA8, 0x4C)

player_atk = (0xD4, 0xCE, 0xC0)
enemy_atk = (0xC8, 0x8A, 0x6E)
player_die = (0xD1, 0x3A, 0x3A)
enemy_die = (0xD8, 0x8A, 0x4A)

needs_target = (0x6C, 0xC8, 0xE0)
status_effect_applied = (0x7A, 0xC0, 0x7A)

# Ambient barks — idle flavour overheard as the player passes near a source
# (a dog, a hamlet, birdsong). A soft mossy grey-green: it reads as background
# atmosphere, dimmer than event lines but warmer than a plain miss.
ambient = (0x7E, 0x88, 0x74)

invalid = (0xE0, 0x6C, 0x4A)
impossible = (0x80, 0x80, 0x80)
error = (0xE0, 0x40, 0x40)

# --- Roll flavour ----------------------------------------------------------
gandalf_rune = (0xF2, 0xE9, 0xC0)   # the auto-success "G" rune
sauron_eye = (0xC4, 0x3A, 0x2A)     # the fell Eye
tengwar = (0xE6, 0xC1, 0x5A)        # a rune (great success)
success_roll = (0xA8, 0xC0, 0x8A)
failure_roll = (0x9A, 0x6A, 0x5A)

# --- Terrain (light = lit by FOV, dark = remembered) -----------------------
# Foreground/background pairs are defined in tile_types; these are shared hues.
wall_light = (0x8C, 0x7A, 0x5C)
wall_dark = (0x35, 0x30, 0x2A)
floor_light = (0x59, 0x54, 0x46)
floor_dark = (0x22, 0x20, 0x1C)

grass_light = (0x5C, 0x74, 0x44)
grass_dark = (0x2A, 0x33, 0x20)
water_light = (0x3C, 0x62, 0x88)
water_dark = (0x1E, 0x2E, 0x40)
road_light = (0x8A, 0x7C, 0x60)
road_dark = (0x3A, 0x34, 0x28)
tree_light = (0x3E, 0x5E, 0x36)
tree_dark = (0x20, 0x2E, 0x1E)

# --- Entities --------------------------------------------------------------
player_c = (0xEC, 0xE4, 0xC8)
ranger_green = (0x6E, 0x8C, 0x52)
npc_c = (0x9A, 0xC0, 0xD8)
orc_c = (0x7C, 0x9A, 0x54)
wolf_c = (0x9A, 0x90, 0x84)
undead_c = (0xB8, 0xC4, 0xC8)
beast_c = (0xB0, 0x86, 0x5A)

item_c = (0xC8, 0xBE, 0x8A)
weapon_c = (0xC0, 0xC6, 0xCE)
herb_c = (0x7A, 0xB8, 0x6E)
gold_c = (0xE0, 0xC0, 0x54)

# --- UI frames -------------------------------------------------------------
frame = (0x5A, 0x54, 0x48)
frame_bright = (0x8A, 0x82, 0x70)
bar_filled = (0x3E, 0x6A, 0x3E)
bar_empty = (0x3A, 0x24, 0x24)
hope_filled = (0xB8, 0x96, 0x3A)
hope_empty = (0x33, 0x2C, 0x18)
xp_filled = (0x4A, 0x6E, 0x9A)
xp_empty = (0x1E, 0x28, 0x38)
menu_title = (0xD8, 0xC8, 0x8A)
menu_text = (0xB8, 0xB2, 0xA6)
selected = (0xF0, 0xE4, 0xB0)

# --- Chrome visual language (CONTEXT.md) ------------------------------------
# The three luminance tiers every line of chrome text belongs to. A Value always
# out-glows its Label; Body is the readable default in between.
tier_label = (0x6C, 0x6E, 0x74)   # dim  — field names, static captions (stone)
tier_body = (0xA2, 0xA4, 0xAA)    # normal — readable prose
tier_value = (0xD8, 0xDA, 0xE0)   # bright — scanned numbers (soft, not glaring)
section_head = (0xCC, 0xB0, 0x5E) # gold — section headers over a rule
rule = (0x48, 0x4A, 0x52)         # thin dim horizontal rule under a header
# Filled bar (reverse-video "this is the thing"): bright text on an accent block.
bar_accent = (0x45, 0x48, 0x54)   # the identity/header/selection block (stone)
# Stateful Value hues — Endurance green→amber→red by fraction of max.
end_full = (0x8A, 0xC0, 0x6E)
end_mid = (0xD8, 0xC0, 0x5A)
end_low = (0xD8, 0x6A, 0x4A)
