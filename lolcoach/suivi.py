"""Mémoire du coach entre deux lectures : timers d'objectifs, achats, vision, jungler adverse."""

from __future__ import annotations

from bisect import bisect_right
from collections import deque

from .etat import ROLES_BOT, Etat, Evenement
from .reglages import Reglages


def _palier(table: list[list[int]], t: float) -> int:
    """Valeur de la dernière ligne [debut, valeur] dont le début est passé."""
    valeur = table[0][1]
    for debut, v in table:
        if t >= debut:
            valeur = v
    return valeur


def vagues_canon_bot(saison: dict, jusqua: float = 3600.0) -> list[float]:
    """Heures d'arrivée en botlane de chaque vague canon."""
    s = saison["sbires"]
    arrivees: list[float] = []
    t = float(s["premiere_vague"])
    depuis_canon = 0
    while t < jusqua:
        depuis_canon += 1
        if depuis_canon >= _palier(s["canon"], t):
            arrivees.append(t + s["trajet_bot"])
            depuis_canon = 0
        t += _palier(s["intervalles"], t)
    return arrivees


def tour_bot(equipe: str) -> str:
    """Nom, dans les événements du jeu, de la tour extérieure bot d'une équipe."""
    return f"Turret_T{1 if equipe == 'ORDER' else 2}_R_03_A"


class Suivi:
    def __init__(self, reglages: Reglages):
        saison = reglages.saison
        self.saison = saison
        self.seuils = reglages.seuils

        self.lectures = 0
        self.nouveaux: list[Evenement] = []
        self._dernier_id = -1

        self.drakes = {"ORDER": 0, "CHAOS": 0}
        self.prochain_drake = float(saison["objectifs"]["drake"])
        self.elder = False
        self.herald_pris = False
        self.prochain_baron = float(saison["objectifs"]["baron"])
        self.tours_tombees: set[str] = set()

        self.nb_achats = 0
        self.dernier_achat = 0.0
        self._valeur: int | None = None
        self.or_seuil_depuis: float | None = None

        self.derniere_vision = 120.0  # pas de rappel avant que le premier ward ait un sens
        self._vision = 0.0

        # (heure, "top" | "mid" | "bot" | "base" | "inconnu", "kill" | "objectif" | "tour" | "retour")
        self.jungler_vu: tuple[float, str, str] | None = None
        self.jungler_vu_ce_tour = False
        self._jungler_mort = False
        self.jungler_nouvelle = float(saison["jungle"]["fin_premier_clear"])

        self.pv: deque[float] = deque(maxlen=5)
        self.mort_ce_tour = False
        self.reapparu_a = 0.0
        self._vivant = True

        self._canons = vagues_canon_bot(saison)

    @property
    def premiere(self) -> bool:
        return self.lectures == 1

    def maj(self, e: Etat) -> None:
        self.lectures += 1
        self.jungler_vu_ce_tour = False

        self.nouveaux = [ev for ev in e.evenements if ev.id > self._dernier_id]
        for ev in self.nouveaux:
            self._evenement(ev, e)
        if self.nouveaux:
            self._dernier_id = self.nouveaux[-1].id
        if self.premiere and e.t > 90:
            # Connexion en cours de partie : on rattrape l'historique sans le commenter.
            self.nouveaux = []
            self.jungler_vu_ce_tour = False

        valeur = e.moi.valeur_objets
        if self._valeur is not None and valeur > self._valeur:
            if e.t - self.dernier_achat > 30 or self.nb_achats == 0:
                self.nb_achats += 1
                self.or_seuil_depuis = None
            self.dernier_achat = e.t
        self._valeur = valeur

        if e.or_ < self.seuils.or_recall:
            self.or_seuil_depuis = None
        elif self.or_seuil_depuis is None:
            self.or_seuil_depuis = e.t

        if e.moi.vision > self._vision + 0.01:
            self.derniere_vision = e.t
        self._vision = e.moi.vision

        jungler = e.jungler_ennemi
        if jungler:
            if jungler.mort:
                self.jungler_nouvelle = e.t
            elif self._jungler_mort:
                self.jungler_vu = (e.t, "base", "retour")
                self.jungler_vu_ce_tour = True
                self.jungler_nouvelle = e.t
            self._jungler_mort = jungler.mort

        self.pv.append(e.pv)
        self.mort_ce_tour = e.moi.mort and self._vivant
        if not e.moi.mort and not self._vivant:
            self.reapparu_a = e.t
        self._vivant = not e.moi.mort

    def _evenement(self, ev: Evenement, e: Etat) -> None:
        o = self.saison["objectifs"]
        jungler = e.jungler_ennemi
        if jungler and jungler.nom in ev.participants:
            self.jungler_nouvelle = ev.t  # un kill, un objectif ou une tour : on sait où il était
            lieu = self._lieu(ev, e, jungler.nom)
            if lieu:
                self.jungler_vu = (ev.t, *lieu)
                self.jungler_vu_ce_tour = True

        if ev.nom == "DragonKill":
            tueur = e.joueur(ev.tueur)
            if ev.type_drake == "Elder":
                self.elder = True
                self.prochain_drake = ev.t + o["elder_respawn"]
                return
            if tueur:
                self.drakes[tueur.equipe] += 1
            if tueur and self.drakes[tueur.equipe] >= o["drakes_pour_ame"]:
                self.elder = True
                self.prochain_drake = ev.t + o["elder_respawn"]
            else:
                self.prochain_drake = ev.t + o["drake_respawn"]
        elif ev.nom == "BaronKill":
            self.prochain_baron = ev.t + o["baron_respawn"]
        elif ev.nom == "HeraldKill":
            self.herald_pris = True
        elif ev.nom == "TurretKilled":
            self.tours_tombees.add(ev.cible)

    @classmethod
    def _lieu(cls, ev: Evenement, e: Etat, jungler: str) -> tuple[str, str] | None:
        """Où un événement place le jungler adverse : (côté de la carte, nature de l'indice)."""
        if ev.nom == "ChampionKill":
            return cls._cote(ev, e, jungler), "kill"
        if ev.nom == "DragonKill":
            return "bot", "objectif"
        if ev.nom in ("HeraldKill", "BaronKill"):
            return "top", "objectif"
        if ev.nom in ("TurretKilled", "InhibKilled"):
            # Turret_T2_R_03_A, Barracks_T2_R1 : le troisième morceau commence par la lane.
            morceaux = ev.cible.split("_")
            lane = {"L": "top", "C": "mid", "R": "bot"}.get(morceaux[2][:1]) if len(morceaux) > 2 else None
            return (lane, "tour") if lane else None
        return None

    @staticmethod
    def _cote(ev: Evenement, e: Etat, jungler: str) -> str:
        # Le kill a lieu là où joue la victime ; si la victime est le jungler, là où joue le tueur.
        for nom in (ev.victime, ev.tueur, *ev.assistants):
            j = e.joueur(nom)
            if j is None or j.nom == jungler:
                continue
            if j.role == "TOP":
                return "top"
            if j.role == "MIDDLE":
                return "mid"
            if j.role in ROLES_BOT:
                return "bot"
        return "inconnu"

    def drake_dispo(self, t: float) -> bool:
        return t >= self.prochain_drake

    def baron_dispo(self, t: float) -> bool:
        return t >= self.prochain_baron

    def en_lane(self, e: Etat) -> bool:
        if e.t >= self.saison["sbires"]["fin_de_lane"]:
            return False
        return not ({tour_bot("ORDER"), tour_bot("CHAOS")} & self.tours_tombees)

    def prochain_canon(self, t: float) -> float:
        """Heure d'arrivée en bot de la prochaine vague canon."""
        i = bisect_right(self._canons, t)
        return self._canons[i] if i < len(self._canons) else float("inf")
