"""Photo typée de la partie, construite depuis le JSON de la Live Client Data API."""

from __future__ import annotations

import re
from dataclasses import dataclass

PINK = 2055
ROLES = ("TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY")  # l'ordre du tableau des scores
ROLES_BOT = ("BOTTOM", "UTILITY")
# « GeneratedTip_SummonerSpell_SummonerFlash_DisplayName » -> « SummonerFlash »
_ID_SORT = re.compile(r"^.*SummonerSpell_(.+?)_DisplayName$")


@dataclass(frozen=True)
class Objet:
    id: int
    nom: str
    prix: int
    nombre: int


@dataclass(frozen=True)
class Sort:
    id: str  # identifiant du jeu : "SummonerFlash", "SummonerDot"...
    nom: str  # nom affiché par le jeu, dans la langue du client


@dataclass(frozen=True)
class Joueur:
    nom: str
    champion: str
    equipe: str  # "ORDER" (bleu) ou "CHAOS" (rouge)
    role: str  # TOP, JUNGLE, MIDDLE, BOTTOM, UTILITY, ou "" si le jeu ne le donne pas
    niveau: int
    mort: bool
    reapparition: float
    kills: int
    morts: int
    assists: int
    cs: int
    vision: float
    objets: tuple[Objet, ...]
    sorts: tuple[Sort, ...]
    arbres: tuple[int, ...]  # identifiants des deux arbres de runes

    @property
    def smite(self) -> bool:
        return any("Smite" in s.id for s in self.sorts)

    @property
    def valeur_objets(self) -> int:
        return sum(o.prix * o.nombre for o in self.objets)

    def possede(self, id_objet: int) -> bool:
        return any(o.id == id_objet for o in self.objets)


@dataclass(frozen=True)
class Evenement:
    id: int
    nom: str
    t: float
    tueur: str = ""
    victime: str = ""
    assistants: tuple[str, ...] = ()
    cible: str = ""  # nom de la tour ou de l'inhibiteur
    type_drake: str = ""

    @property
    def participants(self) -> tuple[str, ...]:
        return tuple(n for n in (self.tueur, self.victime, *self.assistants) if n)


@dataclass(frozen=True)
class Etat:
    t: float
    mode: str
    moi: Joueur
    or_: float
    pv: float  # 0 à 1
    joueurs: tuple[Joueur, ...]
    evenements: tuple[Evenement, ...]

    @property
    def allies(self) -> tuple[Joueur, ...]:
        return tuple(j for j in self.joueurs if j.equipe == self.moi.equipe)

    @property
    def ennemis(self) -> tuple[Joueur, ...]:
        return tuple(j for j in self.joueurs if j.equipe != self.moi.equipe)

    def joueur(self, nom: str) -> Joueur | None:
        court = nom.split("#")[0]
        return next((j for j in self.joueurs if j.nom == court), None)

    def allie(self, role: str) -> Joueur | None:
        return next((j for j in self.allies if j.role == role and j.nom != self.moi.nom), None)

    def ennemi(self, role: str) -> Joueur | None:
        return next((j for j in self.ennemis if j.role == role), None)

    def ennemi_numero(self, numero: int) -> Joueur | None:
        """L'ennemi de la ligne `numero` (1 à 5) du tableau des scores."""
        ennemis = self.ennemis
        if not 1 <= numero <= len(ROLES):
            return None
        if all(j.role for j in ennemis):
            return self.ennemi(ROLES[numero - 1])
        # Partie perso sans rôles : le jeu liste les joueurs dans l'ordre du tableau.
        return ennemis[numero - 1] if numero <= len(ennemis) else None

    @property
    def jungler_ennemi(self) -> Joueur | None:
        # En partie perso le rôle est parfois vide : le Châtiment ne ment pas.
        return self.ennemi("JUNGLE") or next((j for j in self.ennemis if j.smite), None)


def _nom(d: dict) -> str:
    return d.get("riotIdGameName") or d.get("summonerName") or d.get("riotId", "").split("#")[0]


def _joueur(d: dict) -> Joueur:
    scores = d.get("scores", {})
    sorts = d.get("summonerSpells", {})
    return Joueur(
        nom=_nom(d),
        champion=d.get("championName", ""),
        equipe=d.get("team", ""),
        role=d.get("position", "") if d.get("position") != "NONE" else "",
        niveau=int(d.get("level", 1)),
        mort=bool(d.get("isDead", False)),
        reapparition=float(d.get("respawnTimer", 0.0)),
        kills=int(scores.get("kills", 0)),
        morts=int(scores.get("deaths", 0)),
        assists=int(scores.get("assists", 0)),
        cs=int(scores.get("creepScore", 0)),
        vision=float(scores.get("wardScore", 0.0)),
        objets=tuple(
            Objet(int(o.get("itemID", 0)), o.get("displayName", ""), int(o.get("price", 0)), int(o.get("count", 1)))
            for o in d.get("items", [])
        ),
        sorts=tuple(
            Sort(_ID_SORT.sub(r"\1", s.get("rawDisplayName", "")), s.get("displayName", ""))
            for s in sorts.values() if isinstance(s, dict)
        ),
        arbres=tuple(
            int(arbre["id"])
            for cle in ("primaryRuneTree", "secondaryRuneTree")
            if isinstance(arbre := (d.get("runes") or {}).get(cle), dict) and arbre.get("id") is not None
        ),
    )


def _evenement(d: dict) -> Evenement:
    return Evenement(
        id=int(d.get("EventID", 0)),
        nom=d.get("EventName", ""),
        t=float(d.get("EventTime", 0.0)),
        tueur=d.get("KillerName", "").split("#")[0],
        victime=d.get("VictimName", "").split("#")[0],
        assistants=tuple(a.split("#")[0] for a in d.get("Assisters", [])),
        cible=d.get("TurretKilled") or d.get("InhibKilled") or "",
        type_drake=d.get("DragonType", ""),
    )


def depuis_json(brut: dict) -> Etat | None:
    """None si le JSON n'est pas une partie exploitable (chargement, mode spectateur, erreur)."""
    try:
        actif = brut["activePlayer"]
        joueurs = tuple(_joueur(d) for d in brut["allPlayers"])
        jeu = brut["gameData"]
        stats = actif["championStats"]
    except (KeyError, TypeError):
        return None

    moi = next((j for j in joueurs if j.nom == _nom(actif)), None)
    if moi is None:
        return None

    return Etat(
        t=float(jeu.get("gameTime", 0.0)),
        mode=jeu.get("gameMode", ""),
        moi=moi,
        or_=float(actif.get("currentGold", 0.0)),
        pv=float(stats.get("currentHealth", 0.0)) / (float(stats.get("maxHealth", 0.0)) or 1.0),
        joueurs=joueurs,
        evenements=tuple(_evenement(d) for d in brut.get("events", {}).get("Events", [])),
    )
