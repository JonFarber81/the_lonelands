"""Control-flow exceptions."""
from __future__ import annotations


class Impossible(Exception):
    """Raised when an action cannot be performed; the reason is the message."""


class QuitWithoutSaving(SystemExit):
    """Quit the game without triggering an autosave."""
