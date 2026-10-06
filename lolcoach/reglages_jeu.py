"""Vérifie les réglages du jeu que les guides d'ADC recommandent.

Lit le fichier de réglages que League écrit dans son dossier (Config/PersistedSettings.json) : un
simple fichier, pas la mémoire du jeu. Ne modifie rien : il dit ce qui manque, le joueur règle.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .lcu import DOSSIER


@dataclass(frozen=True)
class Constat:
    bon: bool
    nom: str  # le réglage, tel qu'on le cherche dans les options du jeu
    pourquoi: str


# (section, clé, valeur attendue, nom, pourquoi)
OPTIONS = (
    ("General", "EnableTargetedAttackMove", "1", "Attaque-déplacement sur le curseur",
     "sans lui, un clic à côté tape la cible la plus proche de ton champion au lieu de celle que tu vises"),
    ("HUD", "ShowAttackRadius", "1", "Afficher la portée d'attaque",
     "tu vois jusqu'où tu touches : c'est ce qui permet de jouer à la limite de ta portée"),
)
# (événements dont un au moins doit avoir une touche, nom, pourquoi)
TOUCHES = (
    (("evtPlayerAttackMove", "evtPlayerAttackMoveClick"), "Attaque-déplacement",
     "c'est la base du kiting : un clic raté n'envoie plus ton champion marcher dans l'ennemi"),
    (("evtChampionOnly",), "Cibler uniquement les champions",
     "à maintenir quand tu plonges ou que tu vises quelqu'un dans une vague : plus de clic sur un sbire par erreur"),
)


def _liee(valeur: str) -> bool:
    """« [x],[<Unbound>] » : une touche au moins est-elle posée ?"""
    return any(morceau.strip("[] ") not in ("", "<Unbound>") for morceau in str(valeur).split(","))


def verifier(dossier: Path = DOSSIER) -> list[Constat] | None:
    """Un constat par réglage conseillé ; None si le fichier de réglages est introuvable ou illisible."""
    try:
        brut = json.loads((dossier / "Config" / "PersistedSettings.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    valeurs = {
        (section.get("name"), reglage.get("name")): reglage.get("value")
        for fichier in brut.get("files", [])
        for section in fichier.get("sections", [])
        for reglage in section.get("settings", [])
    }
    constats = [Constat(valeurs.get((section, cle)) == attendu, nom, pourquoi) for section, cle, attendu, nom, pourquoi in OPTIONS]
    constats += [
        Constat(any(_liee(valeurs.get(("GameEvents", evenement), "")) for evenement in evenements), f"Touche « {nom} »", pourquoi)
        for evenements, nom, pourquoi in TOUCHES
    ]
    return constats


def rapport(constats: list[Constat] | None) -> str:
    if constats is None:
        return "Réglages du jeu introuvables : League doit être installé dans C:\\Riot Games\\League of Legends."
    lignes = ["Réglages du jeu conseillés pour un ADC :"]
    lignes += [f"  {'ok     ' if c.bon else 'À FAIRE'}  {c.nom}" + ("" if c.bon else f" : {c.pourquoi}") for c in constats]
    return "\n".join(lignes)
