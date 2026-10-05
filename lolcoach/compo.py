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


def _famille(j: Joueur) -> tuple[str, dict]:
    for nom, famille in notes().get("chemins", {}).items():
        if j.cle.lower() in (cle.lower() for cle in famille["champions"]):
            return nom, famille
    return "", {}


def famille_de_build(j: Joueur) -> str:
    """« crit », « on_hit », « kaisa »... ; vide si le champion n'est rangé dans aucune famille."""
    return _famille(j)[0]


def chemin(j: Joueur) -> list[int]:
    """Les trois objets du build type du champion ; vide s'il n'est rangé dans aucune famille."""
    return list(_famille(j)[1].get("objets", []))


def suite(j: Joueur) -> list[int]:
    """Ce qui termine le build quand la partie ne réclame rien de particulier."""
    return list(_famille(j)[1].get("suite", []))


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


def composants_manquants(cible: int, possedes: Iterable[int]) -> list[int]:
    """Ce qu'il reste à acheter pour monter `cible`, à tous les étages de sa recette."""
    sac = Counter(possedes)
    table = objets()
    manquants: list[int] = []

    def parcourir(identifiant: int) -> None:
        for composant in table.get(identifiant, {}).get("recette", []):
            if sac[composant] > 0:
                sac[composant] -= 1
            else:
                manquants.append(composant)
                parcourir(composant)

    parcourir(cible)
    return manquants


def objets_finis(j: Joueur) -> int:
    return sum(o.prix >= PRIX_OBJET_FINI for o in j.objets)
