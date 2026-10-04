"""Enchaîne suivi et règles, puis arbitre : le coach ne dit jamais deux choses contraires.

Chaque règle propose ses conseils sans connaître les autres. L'arbitre regarde ce qu'ils demandent
au joueur (leur intention) et tranche :

- deux intentions contraires : la plus importante passe, l'autre attend ;
- la même intention deux fois de suite : une seule phrase, pas quatre « back » en vingt secondes.

Un conseil écarté n'est pas perdu : s'il est encore vrai quand le conflit est passé, il revient.
"""

from __future__ import annotations

from . import regles, strategie
from .etat import Etat
from .reglages import Reglages
from .regles import Conseil
from .suivi import Suivi

# Du plus important au moins important quand deux intentions s'opposent.
RANG = {"danger": 6, "objectif": 5, "agressif": 4, "tempo": 3, "back": 2, "prudent": 1}
# Ce qui ne peut pas être dit en même temps.
CONTRAIRES = {frozenset(paire) for paire in (
    ("objectif", "back"),  # on ne rentre pas à la base quand un objectif est à prendre
    ("tempo", "back"),  # ni dans la minute qui précède un objectif
    ("objectif", "prudent"),  # la supériorité numérique passe avant la prudence générale
    ("agressif", "prudent"),  # on ne dit pas « force » et « recule » à la suite
    ("danger", "agressif"),
)}
# Secondes pendant lesquelles une intention dite continue de peser sur les suivantes.
PORTEE = 30
# Secondes minimales entre deux conseils de même intention.
ECART = {"danger": 15, "objectif": 12, "agressif": 30, "tempo": 0, "back": 45, "prudent": 40}


class Moteur:
    def __init__(self, reglages: Reglages):
        self.reglages = reglages
        self.suivi = Suivi(reglages)
        self._dits: dict[str, float] = {}  # clé du conseil -> heure où il a été dit
        self._intentions: dict[str, float] = {}  # intention -> dernière heure où elle a été dite

    def lire(self, etat: Etat) -> list[Conseil]:
        """Les conseils à donner pour cette lecture, du plus urgent au moins urgent."""
        self.suivi.maj(etat)
        candidats: list[Conseil] = []
        for regle in regles.REGLES + strategie.REGLES:
            for conseil in regle(etat, self.suivi, self.reglages):
                dit = self._dits.get(conseil.cle)
                if dit is None or (conseil.repeter_apres is not None and etat.t - dit >= conseil.repeter_apres):
                    candidats.append(conseil)
        candidats.sort(key=lambda c: c.priorite)

        if self.suivi.premiere and etat.t > 90:
            # Connexion en cours de partie : ce qui est vrai depuis longtemps est noté comme dit, sans le dire.
            for conseil in candidats:
                self._dits[conseil.cle] = etat.t
            return [c for c in candidats if c.cle == "debut"]

        en_cours = {i for i, dite in self._intentions.items() if etat.t - dite <= PORTEE}
        en_cours |= {c.intention for c in candidats if c.intention}
        retenus: list[Conseil] = []
        prises: set[str] = set()
        for conseil in candidats:
            voulu = conseil.intention
            if voulu:
                if any(frozenset((voulu, autre)) in CONTRAIRES and RANG[autre] > RANG[voulu] for autre in en_cours):
                    continue  # une intention contraire et plus importante est en cours : on attend
                if voulu in prises:
                    self._dits[conseil.cle] = etat.t  # même demande, déjà faite à cette lecture
                    continue
                if etat.t - self._intentions.get(voulu, float("-inf")) < ECART[voulu]:
                    continue  # la même demande vient d'être faite : on attend
                prises.add(voulu)
                self._intentions[voulu] = etat.t
            self._dits[conseil.cle] = etat.t
            retenus.append(conseil)
        return retenus
