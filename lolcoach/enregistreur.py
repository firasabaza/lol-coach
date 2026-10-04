"""Écrit la partie sur disque, une lecture par ligne, pour pouvoir la rejouer au débrief."""

from __future__ import annotations

import gzip
import json
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path


def _alleger(brut: dict, apres_id: int) -> dict:
    """Ne garde que ce que etat.depuis_json lit, et seulement les événements pas encore écrits."""
    actif = brut["activePlayer"]
    stats = actif.get("championStats", {})
    return {
        "activePlayer": {
            "riotIdGameName": actif.get("riotIdGameName"),
            "summonerName": actif.get("summonerName"),
            "riotId": actif.get("riotId"),
            "currentGold": actif.get("currentGold"),
            "championStats": {"currentHealth": stats.get("currentHealth"), "maxHealth": stats.get("maxHealth")},
        },
        "allPlayers": [
            {
                **{k: j.get(k) for k in ("riotIdGameName", "summonerName", "riotId", "championName", "team",
                                         "position", "level", "isDead", "respawnTimer", "scores")},
                "items": [{k: o.get(k) for k in ("itemID", "displayName", "price", "count")}
                          for o in j.get("items", [])],
                "runes": {
                    cle: {"id": arbre.get("id")}
                    for cle, arbre in (j.get("runes") or {}).items()
                    if cle != "keystone" and isinstance(arbre, dict)
                },
                "summonerSpells": {
                    nom: {"rawDisplayName": sort.get("rawDisplayName", ""), "displayName": sort.get("displayName", "")}
                    for nom, sort in j.get("summonerSpells", {}).items() if isinstance(sort, dict)
                },
            }
            for j in brut["allPlayers"]
        ],
        "events": {"Events": [ev for ev in brut.get("events", {}).get("Events", []) if ev.get("EventID", 0) > apres_id]},
        "gameData": {k: brut["gameData"].get(k) for k in ("gameMode", "gameTime")},
    }


class Enregistreur:
    def __init__(self, dossier: Path, champion: str):
        dossier.mkdir(parents=True, exist_ok=True)
        self.chemin = dossier / f"{datetime.now():%Y-%m-%d_%Hh%M%S}_{champion.replace(' ', '')}.jsonl.gz"
        self._fichier = gzip.open(self.chemin, "wt", encoding="utf-8")
        self._dernier_id = -1
        self._lignes = 0

    def ecrire(self, brut: dict) -> None:
        ligne = _alleger(brut, self._dernier_id)
        if ligne["events"]["Events"]:
            self._dernier_id = ligne["events"]["Events"][-1].get("EventID", self._dernier_id)
        self._fichier.write(json.dumps(ligne, ensure_ascii=False, separators=(",", ":")) + "\n")
        self._lignes += 1
        if self._lignes % 10 == 0:
            self._fichier.flush()  # si le coach est coupé net, on ne perd que quelques secondes

    def fermer(self) -> None:
        self._fichier.close()


def relire(chemin: Path) -> Iterator[dict]:
    """Rend chaque lecture enregistrée sous la forme que l'API du jeu avait donnée."""
    evenements: list[dict] = []
    with gzip.open(chemin, "rt", encoding="utf-8") as fichier:
        try:
            for ligne in fichier:
                brut = json.loads(ligne)
                evenements.extend(brut["events"]["Events"])
                brut["events"]["Events"] = list(evenements)
                yield brut
        except (EOFError, json.JSONDecodeError):
            return  # enregistrement coupé net (coach fermé en pleine partie) : on garde ce qu'on a
