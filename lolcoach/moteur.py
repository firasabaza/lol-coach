"""Enchaîne suivi et règles, et ne laisse passer chaque conseil qu'au bon moment."""

from __future__ import annotations

from .etat import Etat
from .reglages import Reglages
from . import regles, strategie
from .regles import Conseil
from .suivi import Suivi


class Moteur:
    def __init__(self, reglages: Reglages):
        self.reglages = reglages
        self.suivi = Suivi(reglages)
        self._dits: dict[str, float] = {}

    def lire(self, etat: Etat) -> list[Conseil]:
        """Les conseils nouveaux pour cette lecture, du plus urgent au moins urgent."""
        self.suivi.maj(etat)
        nouveaux: list[Conseil] = []
        for regle in regles.REGLES + strategie.REGLES:
            for conseil in regle(etat, self.suivi, self.reglages):
                dit = self._dits.get(conseil.cle)
                if dit is not None and (conseil.repeter_apres is None or etat.t - dit < conseil.repeter_apres):
                    continue
                self._dits[conseil.cle] = etat.t
                nouveaux.append(conseil)
        if self.suivi.premiere and etat.t > 90:
            # Connexion en cours de partie : ce qui est vrai depuis longtemps est noté comme dit, sans le dire.
            nouveaux = [c for c in nouveaux if c.cle == "debut"]
        nouveaux.sort(key=lambda c: c.priorite)
        return nouveaux
