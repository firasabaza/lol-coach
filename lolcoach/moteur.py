"""Enchaîne suivi et règles, puis arbitre : le coach ne dit jamais deux choses contraires.

Chaque règle propose ses conseils sans connaître les autres. L'arbitre regarde ce qu'ils demandent
au joueur (leur intention) et tranche :

- deux intentions contraires : la plus importante passe, l'autre attend ;
- la même intention deux fois de suite : une seule phrase, pas quatre « back » en vingt secondes ;
- un joueur bas en PV n'est envoyé ni sur un objectif ni au combat ;
- quand la partie retourne une consigne donnée à l'instant, le coach le dit (« Le back attendra. »).

Un conseil écarté n'est pas perdu : s'il est encore vrai quand le conflit est passé, il revient.
"""

from __future__ import annotations

from dataclasses import replace

from . import regles, strategie
from .etat import Etat
from .reglages import Reglages
from .regles import URGENT, Conseil
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
    ("danger", "objectif"),  # en infériorité ou presque mort, on ne part pas sur un drake
)}
# Ce qu'on ne demande pas à un joueur bas en PV : sa seule décision est de rentrer.
HORS_D_ETAT = {"objectif", "agressif"}
# Secondes pendant lesquelles une intention dite continue de peser sur les suivantes.
PORTEE = 30
# Secondes minimales entre deux conseils de même intention.
ECART = {"danger": 15, "objectif": 12, "agressif": 30, "tempo": 0, "back": 45, "prudent": 40}


def _contraires(a: str, b: str) -> bool:
    return frozenset((a, b)) in CONTRAIRES


def _retournement(voulu: str, annulees: set[str]) -> str:
    """Ce que le coach dit quand il revient sur une consigne qu'il vient de donner."""
    if voulu == "danger":
        return "Stop."
    if "back" in annulees:
        return "Le back attendra."
    return "Changement de plan."


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
        # À priorité égale, l'intention la plus importante d'abord : c'est elle qui parle.
        candidats.sort(key=lambda c: (c.priorite, -RANG.get(c.intention, 0)))

        if self.suivi.premiere and etat.t > 90:
            # Connexion en cours de partie : ce qui est vrai depuis longtemps est noté comme dit, sans le dire.
            for conseil in candidats:
                self._dits[conseil.cle] = etat.t
            return [c for c in candidats if c.cle == "debut"]

        pv = self.suivi.pv
        if not etat.moi.mort and len(pv) == pv.maxlen and max(pv) <= self.reglages.seuils.pv_bas:
            # Bas depuis plusieurs lectures : les conseils qui l'envoient se battre attendent qu'il soit soigné.
            candidats = [c for c in candidats if c.intention not in HORS_D_ETAT]

        souvenirs = {i for i, dite in self._intentions.items() if etat.t - dite <= PORTEE}
        presentes = {c.intention for c in candidats if c.intention}
        retenus: list[Conseil] = []
        prises: set[str] = set()
        for conseil in candidats:
            voulu = conseil.intention
            if voulu:
                urgent = conseil.priorite == URGENT
                # Une consigne urgente est prise sur l'état du moment : ce qui a été dit avant ne la retient pas.
                en_cours = presentes if urgent else presentes | souvenirs
                if any(_contraires(voulu, autre) and RANG[autre] > RANG[voulu] for autre in en_cours):
                    continue  # une intention contraire et plus importante est en cours : on attend
                if voulu in prises or (voulu == "prudent" and "danger" in prises):
                    self._dits[conseil.cle] = etat.t  # même demande, déjà faite à cette lecture
                    continue
                if not urgent and etat.t - self._intentions.get(voulu, float("-inf")) < ECART[voulu]:
                    continue  # la même demande vient d'être faite : on attend
                annulees = {autre for autre in souvenirs - prises if _contraires(voulu, autre)}
                if annulees and voulu != "tempo":  # un minuteur d'objectif informe, il ne retourne rien
                    # Le joueur vient d'entendre le contraire : on lui dit que ça ne tient plus.
                    conseil = replace(conseil, fait=f"{_retournement(voulu, annulees)} {conseil.fait}".strip())
                    for autre in annulees:
                        del self._intentions[autre]
                    souvenirs -= annulees
                prises.add(voulu)
                self._intentions[voulu] = etat.t
            self._dits[conseil.cle] = etat.t
            retenus.append(conseil)
        return retenus
