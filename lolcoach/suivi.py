"""Mémoire du coach entre deux lectures : timers d'objectifs, achats, vision, jungler adverse."""

from __future__ import annotations

import re
from bisect import bisect_right
from collections import deque
from dataclasses import dataclass

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


@dataclass(frozen=True)
class Minuteur:
    """Un sort d'invocateur ennemi que le joueur a vu partir."""

    champion: str
    sort: str  # nom parlé : « Flash », « Ignite »
    note_a: float
    retour: float
    au_plus_tot: bool = False  # calculé en supposant une rune de hâte qu'on ne peut pas voir


# Vu en vraie partie (patch 26.19) : Turret_TChaos_L0_P3_511845594_0.
# L0 = bot, L1 = mid, L2 = top ; P3 = tour extérieure, P2 = intérieure, P1 = d'inhibiteur.
_STRUCTURE = re.compile(r"T(Order|Chaos)_L([012])(?:_P(\d))?")
# Format de la documentation de Riot : Turret_T2_R_03_A, Barracks_T2_R1.
_STRUCTURE_DOC = re.compile(r"T([12])_([LCR])_?(\d+)")


def lire_structure(nom: str) -> tuple[str, str, bool] | None:
    """(équipe propriétaire, lane, tour extérieure ?) d'une tour ou d'un inhibiteur, d'après son nom."""
    if trouve := _STRUCTURE.search(nom):
        return trouve[1].upper(), ("bot", "mid", "top")[int(trouve[2])], trouve[3] == "3"
    if trouve := _STRUCTURE_DOC.search(nom):
        lane = {"L": "top", "C": "mid", "R": "bot"}[trouve[2]]
        return ("ORDER" if trouve[1] == "1" else "CHAOS"), lane, int(trouve[3]) == (5 if lane == "mid" else 3)
    return None


class Suivi:
    def __init__(self, reglages: Reglages):
        saison = reglages.saison
        self.saison = saison
        self.seuils = reglages.seuils

        self.lectures = 0
        self.nouveaux: list[Evenement] = []
        self._dernier_id = -1
        self.decalage = 0.0  # heure de la partie - heure portée par les événements

        self.drakes = {"ORDER": 0, "CHAOS": 0}
        self.prochain_drake = float(saison["objectifs"]["drake"])
        self.elder = False
        self.herald_pris = False
        self.prochain_baron = float(saison["objectifs"]["baron"])
        self.tours_bot_tombees: set[str] = set()  # équipes qui ont perdu leur tour extérieure bot
        # Le jeu arrondit les sbires à la dizaine inférieure : on retient quand chaque dizaine est atteinte.
        self.cs_palier: tuple[int, float] | None = None
        self._cs: int | None = None
        self.morts_ennemies: dict[str, float] = {}  # ennemi actuellement mort -> heure de sa mort

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
        self.kills_a_la_mort: int | None = None  # pour la série de kills en cours
        self.reapparu_a = 0.0
        self._vivant = True

        self._canons = vagues_canon_bot(saison)

        self.sorts: dict[tuple[str, str], Minuteur] = {}  # (joueur, identifiant du sort) -> minuteur
        # Ce que le joueur vient de signaler : ("note" | "annule", Minuteur) ou ("refus", explication).
        self.notes: list[tuple[str, Minuteur | str]] = []
        self._notes_en_attente: list[tuple[str, Minuteur | str]] = []

    @property
    def premiere(self) -> bool:
        return self.lectures == 1

    def noter_sort(self, e: Etat, numero: int, quoi: str) -> None:
        """Le joueur a vu partir un sort de l'ennemi `numero` (ligne du tableau des scores).

        `quoi` vaut "flash" (le Flash, ou le premier sort s'il n'en a pas) ou "autre" (l'autre sort).
        Signaler deux fois le même sort en moins de 10 secondes annule le minuteur.
        """
        cible = e.ennemi_numero(numero)
        if cible is None or not cible.sorts:
            self._notes_en_attente.append(("refus", f"Pas d'ennemi numéro {numero}."))
            return
        flash = next((s for s in cible.sorts if s.id == "SummonerFlash"), cible.sorts[0])
        sort = flash if quoi == "flash" else next((s for s in cible.sorts if s is not flash), flash)
        connu = self.saison["sorts"].get(sort.id, {})
        if "recharge" not in connu:
            self._notes_en_attente.append(("refus", f"Pas de minuteur pour {connu.get('nom', sort.nom)}."))
            return

        cle = (cible.nom, sort.id)
        ancien = self.sorts.get(cle)
        if ancien and e.t - ancien.note_a <= 10:
            del self.sorts[cle]
            self._notes_en_attente.append(("annule", ancien))
            return
        runes = self.saison["hate_runes"]
        inspiration = runes["arbre_inspiration"] in cible.arbres
        hate = sum(self.saison["hate_sorts"].get(str(o.id), 0) for o in cible.objets)
        hate += runes["perspicacite_cosmique"] if inspiration else 0
        retour = e.t + connu["recharge"] * 100 / (100 + hate)
        minuteur = Minuteur(cible.champion, connu["nom"], e.t, retour, au_plus_tot=inspiration)
        self.sorts[cle] = minuteur
        self._notes_en_attente.append(("note", minuteur))

    def maj(self, e: Etat) -> None:
        self.lectures += 1
        self.jungler_vu_ce_tour = False
        self.notes, self._notes_en_attente = self._notes_en_attente, []
        # Un minuteur écoulé reste quelques secondes, le temps que la règle annonce le retour du sort.
        self.sorts = {cle: m for cle, m in self.sorts.items() if e.t - m.retour <= 5}

        self.nouveaux = [ev for ev in e.evenements if ev.id > self._dernier_id]
        if self.nouveaux and not self.premiere:
            # Un événement qui vient d'apparaître date de maintenant : s'il porte une autre heure,
            # c'est que son horloge n'est pas celle de la partie (vu dans l'outil d'entraînement : 37 s d'écart).
            mesure = e.t - self.nouveaux[-1].t
            if abs(mesure - self.decalage) > 5:  # une vraie différence d'horloge, pas la seconde entre deux lectures
                self.decalage = mesure
        for ev in self.nouveaux:
            self._evenement(ev, e)
        if self.nouveaux:
            self._dernier_id = self.nouveaux[-1].id
        self._objectifs(e)
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

        for j in e.ennemis:
            if not j.mort:
                self.morts_ennemies.pop(j.nom, None)
            else:
                self.morts_ennemies.setdefault(j.nom, e.t)

        if self._cs is not None and e.moi.cs > self._cs:
            self.cs_palier = (e.moi.cs, e.t)
        self._cs = e.moi.cs

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
        if self.kills_a_la_mort is None or self.mort_ce_tour:
            self.kills_a_la_mort = e.moi.kills
        if not e.moi.mort and not self._vivant:
            self.reapparu_a = e.t
        self._vivant = not e.moi.mort

    def _evenement(self, ev: Evenement, e: Etat) -> None:
        """Un événement nouveau : dit-il où est le jungler adverse ?"""
        jungler = e.jungler_ennemi
        if jungler and jungler.nom in ev.participants:
            heure = ev.t + self.decalage
            self.jungler_nouvelle = heure  # un kill, un objectif ou une tour : on sait où il était
            lieu = self._lieu(ev, e, jungler.nom)
            if lieu and ev.victime != jungler.nom:  # mort, il n'est plus nulle part : la règle du jungler mort parle
                self.jungler_vu = (heure, *lieu)
                self.jungler_vu_ce_tour = True

    def _objectifs(self, e: Etat) -> None:
        """Recalcule drakes, Baron, Herald et tours depuis tout l'historique, à l'horloge de la partie."""
        o = self.saison["objectifs"]
        self.drakes = {"ORDER": 0, "CHAOS": 0}
        self.prochain_drake, self.elder = float(o["drake"]), False
        self.prochain_baron, self.herald_pris = float(o["baron"]), False
        self.tours_bot_tombees = set()
        for ev in e.evenements:
            heure = ev.t + self.decalage
            if ev.nom == "DragonKill":
                tueur = e.joueur(ev.tueur)
                if tueur and ev.type_drake != "Elder":
                    self.drakes[tueur.equipe] += 1
                ame = tueur is not None and self.drakes[tueur.equipe] >= o["drakes_pour_ame"]
                self.elder = self.elder or ame or ev.type_drake == "Elder"
                self.prochain_drake = heure + (o["elder_respawn"] if self.elder else o["drake_respawn"])
            elif ev.nom == "BaronKill":
                self.prochain_baron = heure + o["baron_respawn"]
            elif ev.nom == "HeraldKill":
                self.herald_pris = True
            elif ev.nom == "TurretKilled":
                structure = lire_structure(ev.cible)
                if structure and structure[1] == "bot" and structure[2]:
                    self.tours_bot_tombees.add(structure[0])

    @classmethod
    def _lieu(cls, ev: Evenement, e: Etat, jungler: str) -> tuple[str, str] | None:
        """Où un événement place le jungler adverse : (côté de la carte, nature de l'indice)."""
        if ev.nom == "ChampionKill":
            return cls._cote(ev, e, jungler), "kill"
        if ev.nom == "DragonKill":
            return "bot", "objectif"
        if ev.nom in ("HeraldKill", "BaronKill", "HordeKill"):  # HordeKill : un grub
            return "top", "objectif"
        if ev.nom in ("TurretKilled", "InhibKilled"):
            structure = lire_structure(ev.cible)
            return (structure[1], "tour") if structure else None
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
        return not self.tours_bot_tombees

    def cs_par_minute(self, e: Etat) -> float:
        """Rythme de farm, mesuré à la dernière dizaine atteinte : c'est le seul instant où le compte est exact."""
        cs, t = self.cs_palier or (e.moi.cs, e.t)
        return cs / (t / 60) if t > 0 else 0.0

    def prochain_canon(self, t: float) -> float:
        """Heure d'arrivée en bot de la prochaine vague canon."""
        i = bisect_right(self._canons, t)
        return self._canons[i] if i < len(self._canons) else float("inf")
