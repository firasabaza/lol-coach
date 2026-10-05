"""Comment le coach dit une durée ou une heure."""

from __future__ import annotations


def duree(secondes: float) -> str:
    s = max(0, round(secondes))
    if s < 60:
        return f"{s} secondes"
    minutes, reste = divmod(s, 60)
    base = "une minute" if minutes == 1 else f"{minutes} minutes"
    return base if reste == 0 else f"{base} {reste}"


def heure(t: float) -> str:
    """Une heure de jeu telle qu'on la dit : « 12 minutes 40 »."""
    minutes, secondes = divmod(max(0, round(t)), 60)
    return f"{minutes} minutes {secondes}" if secondes else f"{minutes} minutes"
