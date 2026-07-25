"""The One Ring character model: the three attributes and eighteen skills,
plus the combat proficiencies. Data-only; the live sheet lives on the Hero
component."""
from __future__ import annotations

# The three attributes. Each maps a rating (2..7) to a Target Number.
ATTRIBUTES = ("Strength", "Heart", "Wits")

# The eighteen common skills, grouped under their governing attribute.
SKILL_GROUPS = {
    "Strength": ["Awe", "Athletics", "Awareness", "Hunting", "Song", "Craft"],
    "Heart": ["Enhearten", "Travel", "Insight", "Healing", "Courtesy", "Battle"],
    "Wits": ["Persuade", "Stealth", "Scan", "Explore", "Riddle", "Lore"],
}

SKILL_TO_ATTR = {
    skill: attr for attr, skills in SKILL_GROUPS.items() for skill in skills
}

ALL_SKILLS = [s for skills in SKILL_GROUPS.values() for s in skills]

# Weapon proficiencies (rated separately from the common skills).
PROFICIENCIES = ("Swords", "Bows", "Spears", "Axes", "Daggers")


def attribute_tn(rating: int) -> int:
    """Higher attribute -> lower TN. TOR2e maps ratings to TNs; we use a clean
    linear approximation: TN = 20 - rating (clamped to a sensible band)."""
    return max(10, min(18, 20 - rating))
