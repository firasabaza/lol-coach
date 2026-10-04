"""Tests de l'après-match sur une partie fabriquée, au format que rend le client League."""

from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from lolcoach.apres_match import rendre
from lolcoach.bilan import DRAKE, analyser, lieu, position
from lolcoach.reglages import charger

REGLAGES = charger()
MOI = 4
# (id, équipe, champion, sorts, lane, rôle) : toi en Kai'Sa côté bleu, Caitlyn et Leona en face.
JOUEURS = [
    (1, 100, 86, (4, 12), "TOP", "SOLO"), (2, 100, 254, (4, 11), "JUNGLE", "NONE"), (3, 100, 103, (4, 14), "MIDDLE", "SOLO"),
    (4, 100, 145, (4, 21), "BOTTOM", "CARRY"), (5, 100, 902, (4, 14), "BOTTOM", "SUPPORT"),
    (6, 200, 122, (4, 12), "TOP", "SOLO"), (7, 200, 64, (4, 11), "JUNGLE", "NONE"), (8, 200, 134, (4, 14), "MIDDLE", "SOLO"),
    (9, 200, 51, (4, 7), "BOTTOM", "CARRY"), (10, 200, 89, (4, 14), "BOTTOM", "SUPPORT"),
]
BASES = {1: (4500, 9500), 2: (4000, 6000), 3: (6500, 6500), 6: (2500, 13000), 7: (11000, 9000), 8: (8200, 8200),
         9: (13300, 4200), 10: (13200, 4000)}


def _ou(joueur: int, minute: int) -> tuple[int, int]:
    if joueur == MOI:  # en botlane, puis mid après 14 minutes, avec un détour seul en toplane à 16-17 minutes
        return (2000, 12400) if minute in (16, 17) else (7000, 7000) if minute >= 14 else (11000, 1500)
    if joueur == 5:  # le support reste avec toi jusqu'à 10 minutes, puis part
        return (11200, 1600) if minute <= 10 else (5000, 5000)
    return BASES[joueur]


def kill(t: int, victime: int, tueur: int, aides: list[int], x: int, y: int) -> dict:
    return {"type": "CHAMPION_KILL", "timestamp": t * 1000, "victimId": victime, "killerId": tueur,
            "assistingParticipantIds": aides, "position": {"x": x, "y": y}, "monsterType": "", "monsterSubType": ""}


EVENEMENTS = [
    kill(400, MOI, 9, [7], 13300, 3800),  # gank en botlane, côté adverse, support à côté
    kill(700, 9, MOI, [5], 12500, 2500), kill(705, 10, MOI, [5], 12600, 2600),  # double kill
    {"type": "ELITE_MONSTER_KILL", "timestamp": 900_000, "killerId": 7, "monsterType": "DRAGON",
     "monsterSubType": "FIRE_DRAGON", "position": {"x": 9866, "y": 4414}, "assistingParticipantIds": []},
    kill(1000, MOI, 6, [], 2000, 12500),  # seul en toplane après la lane
    kill(1100, MOI, 8, [7, 9, 10], 7200, 7200),  # un contre quatre
]


def fabriquer() -> tuple[dict, dict]:
    def stats(joueur: int) -> dict:
        moi = joueur == MOI
        return {"kills": 2 if moi else 1, "deaths": 3 if moi else 1, "assists": 4, "totalMinionsKilled": 120 if moi else 150,
                "neutralMinionsKilled": 0, "goldEarned": 9000, "totalDamageDealtToChampions": 12000 if moi else 15000,
                "visionScore": 10, "visionWardsBoughtInGame": 0, "champLevel": 13, "win": joueur <= 5,
                **{f"item{i}": objet for i, objet in enumerate([1055, 6672, 0, 0, 0, 0, 3340])}}

    partie = {
        "gameId": 42, "queueId": 420, "gameDuration": 1200, "gameCreationDate": "2026-10-03T21:35:00Z",
        "teams": [{"teamId": 100, "win": "Win"}, {"teamId": 200, "win": "Fail"}],
        "participantIdentities": [{"participantId": j[0], "player": {"puuid": "moi" if j[0] == MOI else f"p{j[0]}"}} for j in JOUEURS],
        "participants": [
            {"participantId": i, "teamId": equipe, "championId": champion, "spell1Id": sorts[0], "spell2Id": sorts[1],
             "stats": stats(i), "timeline": {"lane": lane, "role": role}}
            for i, equipe, champion, sorts, lane, role in JOUEURS
        ],
    }
    images = []
    for minute in range(21):
        relevees = {}
        for joueur, *_ in JOUEURS:
            x, y = _ou(joueur, minute)
            total = 500 + (450 if joueur == 9 else 400) * minute
            relevees[str(joueur)] = {"position": {"x": x, "y": y}, "totalGold": total, "currentGold": 300}
        images.append({"timestamp": minute * 60_000, "participantFrames": relevees,
                       "events": [ev for ev in EVENEMENTS if minute * 60 <= ev["timestamp"] / 1000 < (minute + 1) * 60]})
    return partie, {"frames": images}


class Analyse(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bilan = analyser(*fabriquer(), "moi", REGLAGES)

    def test_qui_est_qui(self):
        b = self.bilan
        self.assertEqual((b.moi.champion, b.moi.role), ("Kai'Sa", "adc"))
        self.assertEqual(b.adversaire.champion, "Caitlyn")
        self.assertEqual({j.champion for j in b.joueurs if j.role == "jungle"}, {"Vi", "Lee Sin"})
        self.assertTrue(b.victoire)
        self.assertEqual(b.file, "Classée solo")

    def test_lieux(self):
        self.assertEqual(lieu(*DRAKE, 100), "au drake")
        self.assertEqual(lieu(1000, 1000, 100), "dans ta base")
        self.assertEqual(lieu(1000, 1000, 200), "dans leur base")
        self.assertEqual(lieu(13500, 4000, 100), "en botlane de leur côté")
        self.assertEqual(lieu(4500, 7500, 100), "dans ta jungle")

    def test_position_interpolee_entre_deux_releves(self):
        # De la botlane (minute 13) à la midlane (minute 14) : à mi-chemin à 13:30.
        self.assertEqual(position(self.bilan.images, MOI, 810), (9000.0, 4250.0))

    def test_chaque_mort_a_sa_lecture(self):
        morts = [m for m in self.bilan.moments if m.genre == "mort"]
        self.assertEqual([m.titre for m in morts],
                         ["Mort en botlane de leur côté", "Mort en toplane", "Mort en midlane"])
        gank, isole, surnombre = morts
        self.assertIn("Lee Sin était", gank.analyse)
        self.assertIn("Gank subi", gank.conseil)
        self.assertEqual(gank.acteurs, ["Caitlyn", "LeeSin"])
        self.assertIn("Seul loin de ton équipe", isole.conseil)
        self.assertIn("4 contre 2", surnombre.analyse)  # ton midlaner était à côté
        self.assertIn("perdu d'avance", surnombre.conseil)

    def test_bon_moment_et_objectif_joue_sans_moi(self):
        genres = [(m.genre, round(m.t)) for m in self.bilan.moments]
        self.assertIn(("exploit", 700), genres)
        cede = next(m for m in self.bilan.moments if m.genre == "objectif")
        self.assertEqual((cede.titre, round(cede.t)), ("Drake cédé", 900))
        self.assertIn("en midlane", cede.analyse)

    def test_lecons_et_chiffres(self):
        b = self.bilan
        self.assertEqual(b.chiffres["cs_par_minute"], 6.0)
        self.assertEqual(b.chiffres["ecart_or_14"], -700)
        titres = [lecon.titre for lecon in b.lecons]
        # Les quatre plus coûteuses seulement : la vision et le farm, moins graves ici, restent dehors.
        self.assertEqual(len(titres), 4)
        for attendu in ("Dégâts en combat", "Morts loin de l'équipe", "Combats perdus d'avance", "Ganks subis"):
            self.assertIn(attendu, titres)
        self.assertEqual(titres, [lecon.titre for lecon in sorted(b.lecons, key=lambda lecon: -lecon.poids)])


class Page(unittest.TestCase):
    def test_la_page_contient_tout(self):
        bilan = analyser(*fabriquer(), "moi", REGLAGES)
        with tempfile.TemporaryDirectory() as dossier:
            html = rendre(bilan, REGLAGES, Path(dossier), coach="<ol class='timeline'><li>Drake dans une minute.</li></ol>")
        for attendu in ("Victoire", "Kai&#x27;Sa", "À améliorer", "Moments clés", "Revue de carte", "Les dix joueurs",
                        "Or total", "Ce que le coach a dit", 'data-id="4"', "Voir sur la carte", "Lee Sin"):
            self.assertIn(attendu, html)
        carte = json.loads(re.search(r'id="donnees-carte">(.*?)</script>', html, re.S).group(1))
        self.assertEqual(len(carte["images"]), 21)
        self.assertEqual(len(carte["kills"]), 5)
        self.assertEqual(carte["objectifs"][0]["nom"], "Drake")


if __name__ == "__main__":
    unittest.main()
