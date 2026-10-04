"""Faux serveur de jeu : rejoue une partie d'ADC écrite à l'avance, au format de l'API du jeu.

    python -m lolcoach.simulateur --vitesse 30

Sert à tester le coach sans lancer League of Legends.
"""

from __future__ import annotations

import argparse
import json
import threading
import time
from bisect import bisect_right
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 29990
FIN = 1290.0

MOI = "Joueur"
JOUEURS = [
    # (nom, champion, équipe, rôle, châtiment)
    (MOI, "Jinx", "ORDER", "BOTTOM", False),
    ("Lulu allié", "Lulu", "ORDER", "UTILITY", False),
    ("Vi allié", "Vi", "ORDER", "JUNGLE", True),
    ("Ahri allié", "Ahri", "ORDER", "MIDDLE", False),
    ("Garen allié", "Garen", "ORDER", "TOP", False),
    ("Caitlyn ennemie", "Caitlyn", "CHAOS", "BOTTOM", False),
    ("Leona ennemie", "Leona", "CHAOS", "UTILITY", False),
    ("Lee Sin ennemi", "Lee Sin", "CHAOS", "JUNGLE", True),
    ("Syndra ennemie", "Syndra", "CHAOS", "MIDDLE", False),
    ("Darius ennemi", "Darius", "CHAOS", "TOP", False),
]

DORAN = (1055, "Lame de Doran", 450)
BF = (1038, "B.F. Glaive", 1300)
EPEE = (1036, "Épée longue", 350)
PIOCHE = (1037, "Pioche", 875)
BOTTES = (1001, "Bottes", 300)
CAPE = (1018, "Cape d'agilité", 600)

# Inventaires : (à partir de t, objets)
OBJETS = {
    MOI: [(5, [DORAN]), (400, [DORAN, BF, EPEE]), (795, [DORAN, BF, EPEE, PIOCHE, BOTTES])],
    "Caitlyn ennemie": [
        (5, [DORAN]),
        (310, [DORAN, BF, BOTTES]),
        (640, [DORAN, BF, BOTTES, PIOCHE, CAPE, EPEE]),
    ],
}

# Niveaux : heures de passage des niveaux 2, 3, 4...
NIVEAUX = {
    MOI: [104, 160, 250, 330, 420, 520, 620, 720, 840, 960, 1080, 1200],
    "Caitlyn ennemie": [95, 165, 245, 335, 430, 530, 630, 730, 850, 970, 1090, 1210],
    "Leona ennemie": [97, 175, 270, 370, 470, 580, 700, 830, 960, 1100, 1240],
    "Lee Sin ennemi": [115, 150, 230, 360, 500, 620, 740, 870, 1000, 1140],
}
NIVEAUX_DEFAUT = [100, 170, 250, 340, 440, 540, 650, 760, 880, 1000, 1130, 1260]

# Courbes linéaires par morceaux : (t, valeur)
OR = [(0, 500), (4.9, 500), (5, 0), (65, 0), (280, 960), (281, 1260), (399.9, 1714), (400, 64),
      (556, 640), (558, 1090), (760, 1580), (794.9, 1650), (795, 475), (1290, 2400)]
PV = [(0, 1.0), (300, 0.9), (330, 0.30), (395, 0.28), (402, 1.0), (750, 0.8), (760, 0.0),
      (785, 0.0), (786, 1.0), (1290, 0.9)]
CS = [(0, 0), (63, 0), (1290, 127)]
VISION = [(0, 0.0), (130, 0.0), (131, 1.0), (220, 2.5), (600, 2.5), (601, 3.5), (700, 5.0), (1290, 14.0)]

# Morts : (nom, heure, durée)
MORTS = [
    ("Garen allié", 200, 12), ("Caitlyn ennemie", 280, 14),
    ("Caitlyn ennemie", 556, 22), ("Leona ennemie", 558, 20), (MOI, 760, 25),
    ("Syndra ennemie", 1095, 34), ("Darius ennemi", 1097, 34), ("Lee Sin ennemi", 1100, 36),
]

EVENEMENTS = [
    {"EventName": "GameStart", "EventTime": 0.0},
    {"EventName": "MinionsSpawning", "EventTime": 30.0},
    {"EventName": "ChampionKill", "EventTime": 200.0, "KillerName": "Lee Sin ennemi",
     "VictimName": "Garen allié", "Assisters": ["Darius ennemi"]},
    {"EventName": "FirstBlood", "EventTime": 200.0, "Recipient": "Lee Sin ennemi"},
    {"EventName": "ChampionKill", "EventTime": 280.0, "KillerName": MOI,
     "VictimName": "Caitlyn ennemie", "Assisters": ["Lulu allié"]},
    {"EventName": "DragonKill", "EventTime": 372.0, "DragonType": "Fire", "Stolen": "False",
     "KillerName": "Lee Sin ennemi", "Assisters": ["Syndra ennemie"]},
    {"EventName": "ChampionKill", "EventTime": 556.0, "KillerName": MOI,
     "VictimName": "Caitlyn ennemie", "Assisters": ["Lulu allié", "Vi allié"]},
    {"EventName": "ChampionKill", "EventTime": 558.0, "KillerName": "Vi allié",
     "VictimName": "Leona ennemie", "Assisters": [MOI, "Lulu allié"]},
    {"EventName": "TurretKilled", "EventTime": 700.0, "TurretKilled": "Turret_T2_R_03_A",
     "KillerName": MOI, "Assisters": ["Lulu allié"]},
    {"EventName": "FirstBrick", "EventTime": 700.0, "KillerName": MOI},
    {"EventName": "DragonKill", "EventTime": 705.0, "DragonType": "Earth", "Stolen": "False",
     "KillerName": "Vi allié", "Assisters": [MOI]},
    {"EventName": "ChampionKill", "EventTime": 760.0, "KillerName": "Lee Sin ennemi",
     "VictimName": MOI, "Assisters": ["Caitlyn ennemie", "Leona ennemie"]},
    {"EventName": "ChampionKill", "EventTime": 1095.0, "KillerName": "Ahri allié",
     "VictimName": "Syndra ennemie", "Assisters": [MOI]},
    {"EventName": "ChampionKill", "EventTime": 1097.0, "KillerName": "Garen allié",
     "VictimName": "Darius ennemi", "Assisters": ["Vi allié"]},
    {"EventName": "ChampionKill", "EventTime": 1100.0, "KillerName": MOI,
     "VictimName": "Lee Sin ennemi", "Assisters": ["Lulu allié", "Ahri allié"]},
    {"EventName": "GameEnd", "EventTime": FIN, "Result": "Win"},
]


def _courbe(points: list[tuple[float, float]], t: float) -> float:
    if t <= points[0][0]:
        return points[0][1]
    for (t0, v0), (t1, v1) in zip(points, points[1:]):
        if t <= t1:
            return v0 + (v1 - v0) * (t - t0) / (t1 - t0)
    return points[-1][1]


def _palier(paliers: list[tuple[float, list]], t: float) -> list:
    i = bisect_right([p[0] for p in paliers], t)
    return paliers[i - 1][1] if i else []


def _joueur(nom: str, champion: str, equipe: str, role: str, smite: bool, t: float) -> dict:
    mort = next((m for m in MORTS if m[0] == nom and m[1] <= t < m[1] + m[2]), None)
    evenements = [e for e in EVENEMENTS if e["EventName"] == "ChampionKill" and e["EventTime"] <= t]
    sort_d, nom_d = ("SummonerSmite", "Châtiment") if smite else ("SummonerDot", "Embrasement")
    return {
        "championName": champion,
        "isBot": False,
        "isDead": mort is not None,
        "items": [
            {"itemID": i, "displayName": n, "price": p, "count": 1, "slot": slot,
             "canUse": False, "consumable": False}
            for slot, (i, n, p) in enumerate(_palier(OBJETS.get(nom, [(5, [DORAN])]), t))
        ],
        "level": 1 + bisect_right(NIVEAUX.get(nom, NIVEAUX_DEFAUT), t),
        "position": role,
        "respawnTimer": round(mort[1] + mort[2] - t, 1) if mort else 0.0,
        "riotId": f"{nom}#EUW",
        "riotIdGameName": nom,
        "riotIdTagLine": "EUW",
        "summonerName": nom,
        "scores": {
            "kills": sum(e["KillerName"] == nom for e in evenements),
            "deaths": sum(e["VictimName"] == nom for e in evenements),
            "assists": sum(nom in e["Assisters"] for e in evenements),
            "creepScore": int(_courbe(CS, t)) if nom == MOI else int(max(0.0, t - 63) * 0.11),
            "wardScore": round(_courbe(VISION, t), 2) if nom == MOI else round(t / 60, 2),
        },
        "summonerSpells": {
            "summonerSpellOne": {"displayName": "Saut éclair",
                                 "rawDisplayName": "GeneratedTip_SummonerSpell_SummonerFlash_DisplayName"},
            "summonerSpellTwo": {"displayName": nom_d,
                                 "rawDisplayName": f"GeneratedTip_SummonerSpell_{sort_d}_DisplayName"},
        },
        "team": equipe,
    }


def partie(t: float) -> dict:
    """Ce que l'API du jeu renverrait à l'instant t de la partie scénarisée."""
    t = min(t, FIN)
    joueurs = [_joueur(*j, t) for j in JOUEURS]
    return {
        "activePlayer": {
            "championStats": {"currentHealth": round(1800 * _courbe(PV, t), 1), "maxHealth": 1800.0,
                              "resourceValue": 300.0, "resourceMax": 400.0, "resourceType": "MANA"},
            "currentGold": round(_courbe(OR, t), 1),
            "level": joueurs[0]["level"],
            "riotId": f"{MOI}#EUW",
            "riotIdGameName": MOI,
            "summonerName": MOI,
        },
        "allPlayers": joueurs,
        "events": {"Events": [{"EventID": i, **e} for i, e in enumerate(EVENEMENTS) if e["EventTime"] <= t]},
        "gameData": {"gameMode": "CLASSIC", "gameTime": round(t, 2), "mapName": "Map11",
                     "mapNumber": 11, "mapTerrain": "Default"},
    }


class Serveur:
    """Sert la partie scénarisée en HTTP, à une vitesse accélérée."""

    def __init__(self, vitesse: float = 30.0, port: int = PORT, depart: float = 0.0):
        debut = time.monotonic()

        class Requete(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                t = depart + (time.monotonic() - debut) * vitesse
                if self.path != "/liveclientdata/allgamedata" or t > FIN + 5 * vitesse:
                    self.send_error(404)
                    return
                corps = json.dumps(partie(t)).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(corps)))
                self.end_headers()
                self.wfile.write(corps)

            def log_message(self, *args: object) -> None:
                pass

        self._http = ThreadingHTTPServer(("127.0.0.1", port), Requete)
        self.url = f"http://127.0.0.1:{self._http.server_port}"

    def demarrer(self) -> None:
        threading.Thread(target=self._http.serve_forever, daemon=True).start()

    def arreter(self) -> None:
        self._http.shutdown()
        self._http.server_close()


if __name__ == "__main__":
    arguments = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    arguments.add_argument("--vitesse", type=float, default=30.0)
    arguments.add_argument("--port", type=int, default=PORT)
    options = arguments.parse_args()
    serveur = Serveur(options.vitesse, options.port)
    print(f"Partie simulée sur {serveur.url} (x{options.vitesse:g}). Ctrl+C pour arrêter.")
    serveur.demarrer()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        serveur.arreter()
