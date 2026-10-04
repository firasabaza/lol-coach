"""Charge config.toml (réglages du joueur) et donnees/saison.toml (timers du jeu)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
NIVEAUX = ("coach", "faits", "silencieux")


@dataclass(frozen=True)
class Seuils:
    or_recall: int = 1300
    or_dormant: int = 2000
    or_reset_objectif: int = 900
    pv_bas: float = 0.35
    pv_critique: float = 0.20
    vision_silence: int = 150
    jungler_inconnu: int = 75
    cs_par_minute: float = 7.0
    ecart_items: int = 700
    annonces_objectif: tuple[int, ...] = (60, 30)


@dataclass(frozen=True)
class Reglages:
    saison: dict
    niveau: str = "coach"
    seuils: Seuils = field(default_factory=Seuils)
    voix: dict = field(default_factory=dict)
    fenetre: dict = field(default_factory=dict)
    sorts: dict = field(default_factory=dict)


def _lire(chemin: Path) -> dict:
    with chemin.open("rb") as f:
        return tomllib.load(f)


def charger(racine: Path = RACINE) -> Reglages:
    saison = _lire(racine / "donnees" / "saison.toml")
    chemin = racine / "config.toml"
    config = _lire(chemin) if chemin.exists() else {}

    niveau = config.get("niveau", "coach")
    if niveau not in NIVEAUX:
        raise ValueError(f"config.toml : niveau = {niveau!r} inconnu, choisis parmi {', '.join(NIVEAUX)}")

    connus = {f.name for f in fields(Seuils)}
    lus = config.get("seuils", {})
    inconnus = set(lus) - connus
    if inconnus:
        raise ValueError(f"config.toml : seuils inconnus : {', '.join(sorted(inconnus))}")
    if "annonces_objectif" in lus:
        lus = {**lus, "annonces_objectif": tuple(lus["annonces_objectif"])}

    return Reglages(
        saison=saison,
        niveau=niveau,
        seuils=Seuils(**lus),
        voix=config.get("voix", {}),
        fenetre=config.get("fenetre", {}),
        sorts=config.get("sorts", {}),
    )
