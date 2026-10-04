"""Ce que les champions de la partie changent au plan : matchup, composition adverse, build.

Les classes viennent de donnees/champions.json (Meraki Analytics), les listes fines et les chemins
d'items de donnees/champions_notes.toml (tenues à la main).
"""

from __future__ import annotations

import tomllib
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache

from .datadragon import champions, objets
from .etat import PRIX_OBJET_FINI, Etat, Joueur
from .reglages import RACINE

TANKS = {"TANK", "VANGUARD", "WARDEN", "JUGGERNAUT"}
PLONGEURS = {"ASSASSIN", "DIVER", "SKIRMISHER"}
POKE = {"ARTILLERY"}


@cache
def notes() -> dict:
    try:
        with (RACINE / "donnees" / "champions_notes.toml").open("rb") as f:
            return tomllib.load(f)
    except OSError:
        return {}


@cache
def _fiches() -> dict[str, dict]:
    return {cle.lower(): fiche for cle, fiche in champions().items()}


@cache
def _liste(nom: str) -> frozenset[str]:
    return frozenset(cle.lower() for cle in notes().get(nom, []))


def fiche(j: Joueur) -> dict:
    """Classe, portée et type de dégâts du champion ; vide s'il est inconnu."""
    return _fiches().get(j.cle.lower(), {})


def est(j: Joueur, liste: str) -> bool:
    """Le champion figure-t-il dans une liste de champions_notes.toml (soins, accroches...) ?"""
    return j.cle.lower() in _liste(liste)


def classe(j: Joueur, roles: set[str]) -> bool:
    return bool(roles & set(fiche(j).get("roles", [])))


def noms(joueurs: Iterable[Joueur]) -> str:
    """« Zed », « Zed et Rengar », « Zed, Rengar et Vi »."""
    liste = [j.champion for j in joueurs]
    return liste[0] if len(liste) == 1 else f"{', '.join(liste[:-1])} et {liste[-1]}" if liste else ""


@dataclass(frozen=True)
class Compo:
    """L'équipe adverse, vue par un ADC."""

    ad: tuple[Joueur, ...]
    ap: tuple[Joueur, ...]
    tanks: tuple[Joueur, ...]
    plongeurs: tuple[Joueur, ...]  # assassins et bruisers qui viennent sur le carry
    soigneurs: tuple[Joueur, ...]
    suppressions: tuple[Joueur, ...]
    controles: tuple[Joueur, ...]
    poke: tuple[Joueur, ...]
    ultis_engage: tuple[Joueur, ...]


def lire_compo(e: Etat) -> Compo:
    ennemis = e.ennemis

    def filtre(test) -> tuple[Joueur, ...]:
        return tuple(j for j in ennemis if test(j))

    return Compo(
        ad=filtre(lambda j: fiche(j).get("degats") == "AD"),
        ap=filtre(lambda j: fiche(j).get("degats") == "AP"),
        tanks=filtre(lambda j: classe(j, TANKS)),
        plongeurs=filtre(lambda j: classe(j, PLONGEURS)),
        soigneurs=filtre(lambda j: est(j, "soins")),
        suppressions=filtre(lambda j: est(j, "suppressions")),
        controles=filtre(lambda j: est(j, "controles")),
        poke=filtre(lambda j: classe(j, POKE)),
        ultis_engage=filtre(lambda j: est(j, "ultis_engage")),
    )


# --- Build ---------------------------------------------------------------------------------------


def nom_objet(identifiant: int) -> str:
    return objets().get(identifiant, {}).get("nom", f"objet {identifiant}")


def chemin(j: Joueur) -> list[int]:
    """Le chemin d'items type du champion ; vide s'il n'est rangé dans aucune famille."""
    for famille in notes().get("chemins", {}).values():
        if j.cle.lower() in (cle.lower() for cle in famille["champions"]):
            return list(famille["objets"])
    return []


def reste_a_payer(cible: int, possedes: Iterable[int]) -> int:
    """Or qu'il manque pour finir `cible`, composants déjà en poche déduits."""
    sac = Counter(possedes)
    table = objets()

    def cout(identifiant: int) -> int:
        if sac[identifiant] > 0:
            sac[identifiant] -= 1
            return 0
        connu = table.get(identifiant)
        if connu is None:
            return 0
        recette = connu.get("recette", [])
        combinaison = connu["prix"] - sum(table.get(c, {}).get("prix", 0) for c in recette)
        return combinaison + sum(cout(c) for c in recette)

    return cout(cible)


def objets_finis(j: Joueur) -> int:
    return sum(o.prix >= PRIX_OBJET_FINI for o in j.objets)


def adaptations(e: Etat) -> list[tuple[int, str]]:
    """Objets que la compo adverse justifie, du plus pressant au moins pressant : (objet, raison)."""
    table = notes().get("adaptation")
    if not table:
        return []
    c = lire_compo(e)
    magique = fiche(e.moi).get("degats") == "AP"  # Kai'Sa et les ADC qui partent en AP
    proposes: list[tuple[int, str]] = []

    if c.suppressions and not (e.moi.possede(table["ceinture"]) or e.moi.possede(3139)):
        proposes.append((table["ceinture"], f"{noms(c.suppressions)} te sort du combat d'un sort"))
    if len(c.soigneurs) >= 2 and not (e.moi.possede(table["anti_soin"]) or e.moi.possede(table["anti_soin_fini"])):
        proposes.append((table["anti_soin"], f"soins de {noms(c.soigneurs)}"))
    blindes = [j for j in e.ennemis if sum(objets().get(o.id, {}).get("armure", 0) for o in j.objets) >= 90]
    if (len(c.tanks) >= 2 or blindes) and not magique and not e.moi.possede(table["anti_tank"]):
        raison = f"{noms(blindes)} empile l'armure" if blindes else f"{len(c.tanks)} tanks en face"
        proposes.append((table["anti_tank"], raison))
    nourris = [j for j in c.plongeurs if j.kills >= 4 and j.kills - j.morts >= 3]
    if nourris or len(c.plongeurs) >= 3:
        survie = 3157 if magique else table["survie"]  # Sablier de Zhonya pour un build AP
        if not e.moi.possede(survie):
            raison = f"{noms(nourris)} te tue en un combo" if nourris else f"{noms(c.plongeurs)} plongent sur toi"
            proposes.append((survie, raison))
    if len(c.ap) >= 3 and not magique and not e.moi.possede(table["anti_ap"]):
        proposes.append((table["anti_ap"], f"{len(c.ap)} sources de dégâts magiques"))
    return proposes


def bottes(e: Etat) -> tuple[int, str] | None:
    """Des bottes défensives, si la compo adverse les justifie ; None pour les bottes habituelles."""
    table = notes().get("adaptation")
    if not table:
        return None
    c = lire_compo(e)
    if len(c.controles) + len(c.suppressions) >= 3:
        return table["bottes_cc"], f"{len(c.controles) + len(c.suppressions)} contrôles en face"
    tueurs_ad = [j for j in c.plongeurs if j in c.ad]
    if len(c.ad) >= 4 and tueurs_ad:
        return table["bottes_ad"], f"{len(c.ad)} champions à dégâts physiques, dont {noms(tueurs_ad)}"
    return None
