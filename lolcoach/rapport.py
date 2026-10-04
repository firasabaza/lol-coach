"""Rapport de force : où en est le joueur face à chaque ennemi, et dans la partie.

Tous les conseils passent par là. On ne dit pas « recule » à un carry qui a 2000 gold d'avance,
ni « force le trade » à quelqu'un qui en a 2000 de retard.
"""

from __future__ import annotations

from statistics import mean

from .etat import ROLES_BOT, Etat, Joueur

NET = 800  # écart de puissance à partir duquel un duel est clairement joué
ECRASANT = 2000  # écart à partir duquel on peut se battre à un contre deux


def or_gagne(j: Joueur, t: float) -> float:
    """Or gagné depuis le début, estimé d'après le tableau des scores."""
    return 500 + max(0.0, t - 65) * 2.04 + 21 * j.cs + 300 * j.kills + 120 * j.assists


def puissance(e: Etat, j: Joueur) -> float:
    """Force de combat approximative : or transformé en objets, plus les niveaux.

    Les objets d'un ennemi ne sont connus que quand il a été vu : on ne descend pas sous ce que
    son score laisse supposer.
    """
    objets = j.valeur_objets if j.nom == e.moi.nom else max(j.valeur_objets, 0.75 * or_gagne(j, e.t))
    return objets + 300 * j.niveau


def avance(e: Etat, ennemi: Joueur) -> float:
    """Avance du joueur sur un ennemi, en gold de puissance. Négative s'il est derrière."""
    return puissance(e, e.moi) - puissance(e, ennemi)


def avance_lane(e: Etat) -> float:
    """Avance sur le plus fort des deux adversaires de lane (0 si on ne les connaît pas)."""
    duo = [j for j in e.ennemis if j.role in ROLES_BOT]
    return min((avance(e, j) for j in duo), default=0.0)


def forme(e: Etat) -> str:
    """« domine », « retard » ou « normal » : l'état du joueur dans la partie."""
    if not e.ennemis:
        return "normal"
    ecart = puissance(e, e.moi) + 0.5 * e.or_ - mean(puissance(e, j) for j in e.ennemis)
    bilan = e.moi.kills - e.moi.morts
    if ecart >= 1500 or (bilan >= 4 and e.moi.kills >= 5 and ecart >= 0):
        return "domine"
    if ecart <= -1500 or (bilan <= -4 and ecart <= 0):
        return "retard"
    return "normal"


def ennemis_morts(e: Etat) -> int:
    return sum(j.mort for j in e.ennemis)


def score(j: Joueur) -> str:
    return f"{j.kills}/{j.morts}/{j.assists}"
