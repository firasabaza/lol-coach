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


def or_en_poche(e: Etat) -> float:
    """L'or que le joueur peut encore transformer en puissance.

    Zéro quand le build est fini (il n'y a plus rien à acheter), et quand l'outil d'entraînement
    en a donné des dizaines de milliers.
    """
    if e.moi.build_complet or (e.mode == "PRACTICETOOL" and e.or_ > 10000):
        return 0.0
    return e.or_


def objets_estimes(e: Etat, j: Joueur) -> float:
    """Valeur des objets d'un joueur. Ceux d'un ennemi ne sont connus que quand il a été vu :
    on ne descend pas sous ce que son score laisse supposer."""
    return j.valeur_objets if j.nom == e.moi.nom else max(j.valeur_objets, 0.75 * or_gagne(j, e.t))


def puissance(e: Etat, j: Joueur) -> float:
    """Force de combat approximative : or transformé en objets, plus les niveaux."""
    return objets_estimes(e, j) + 300 * j.niveau


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
    if (ecart >= 1500 and bilan >= 0) or (bilan >= 4 and e.moi.kills >= 5 and ecart >= 0):
        return "domine"
    if ecart <= -1500 or (bilan <= -4 and ecart <= 0):
        return "retard"
    return "normal"


def ennemis_morts(e: Etat) -> int:
    return sum(j.mort for j in e.ennemis)


def vivants(e: Etat) -> tuple[int, int]:
    """(alliés en vie, ennemis en vie), le joueur compris."""
    return sum(not j.mort for j in e.allies), sum(not j.mort for j in e.ennemis)


def nourri(j: Joueur) -> bool:
    """Un joueur dont le score suffit à en faire une menace."""
    return j.kills >= 4 and j.kills - j.morts >= 3


def peut_presser(e: Etat, marge: float = NET / 2) -> bool:
    """Le joueur est-il en état de chercher le combat en lane ?

    Pas en retard de plus de `marge` (la puissance d'un ennemi est estimée par excès tant qu'il n'a
    pas dépensé son or), pas après deux morts précoces, pas avec trois morts de plus que de kills,
    pas face à un adversaire de lane nourri qu'il ne domine pas.
    """
    bilan = e.moi.kills - e.moi.morts
    morts_precoces = e.t < 600 and e.moi.morts >= 2 and bilan < 0
    menace = any(nourri(j) and avance(e, j) < NET for j in e.ennemis if j.role in ROLES_BOT)
    return avance_lane(e) > -marge and forme(e) != "retard" and not morts_precoces and bilan > -3 and not menace


def drake_jouable(e: Etat) -> bool:
    """Un drake se prend avec son jungler en vie, et pas en infériorité."""
    jungler = next((j for j in e.allies if j.role == "JUNGLE" or j.smite), None)
    nous, eux = vivants(e)
    return jungler is not None and not jungler.mort and nous >= eux


def score(j: Joueur) -> str:
    return f"{j.kills}/{j.morts}/{j.assists}"
