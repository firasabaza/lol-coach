"""Tests du coach sur la partie simulée. Lancer : python -m unittest discover -s tests"""

from __future__ import annotations

import contextlib
import io
import tempfile
import threading
import time
import unittest
from dataclasses import replace
from pathlib import Path

from lolcoach import simulateur
from lolcoach.__main__ import Coach, _hors_profil
from lolcoach.client import Client
from lolcoach.debrief import generer
from lolcoach.enregistreur import Enregistreur, relire
from lolcoach.etat import depuis_json
from lolcoach.moteur import Moteur
from lolcoach.reglages import RACINE, charger
from lolcoach.regles import Conseil, duree
from lolcoach.suivi import Suivi, vagues_canon_bot

REGLAGES = replace(charger(), niveau="coach")


def jouer(debut: int = 0, fin: int = int(simulateur.FIN)) -> list[tuple[int, Conseil]]:
    """Tous les conseils du moteur sur la partie simulée, une lecture par seconde."""
    moteur = Moteur(REGLAGES)
    conseils = []
    for t in range(debut, fin + 1):
        conseils += [(t, c) for c in moteur.lire(depuis_json(simulateur.partie(t)))]
    return conseils


class Etat(unittest.TestCase):
    def test_lecture_de_la_partie(self):
        e = depuis_json(simulateur.partie(300))
        self.assertEqual(e.moi.champion, "Jinx")
        self.assertEqual(len(e.ennemis), 5)
        self.assertEqual(e.jungler_ennemi.champion, "Lee Sin")
        self.assertEqual(e.ennemi("BOTTOM").champion, "Caitlyn")
        self.assertEqual(e.allie("UTILITY").champion, "Lulu")

    def test_jungler_reconnu_au_chatiment_quand_le_role_manque(self):
        brut = simulateur.partie(300)
        for joueur in brut["allPlayers"]:
            joueur["position"] = "NONE"
        self.assertEqual(depuis_json(brut).jungler_ennemi.champion, "Lee Sin")

    def test_json_inexploitable(self):
        self.assertIsNone(depuis_json({"errorCode": "RESOURCE_NOT_FOUND", "httpStatus": 404}))
        spectateur = simulateur.partie(300)
        spectateur["activePlayer"] = {"error": "Spectator mode doesn't currently support this feature"}
        self.assertIsNone(depuis_json(spectateur))


class Horloge(unittest.TestCase):
    def test_vagues_canon(self):
        arrivees = vagues_canon_bot(REGLAGES.saison)
        # Vagues à 0:30, 1:00, 1:30 : la troisième porte le canon, 33 s de trajet.
        self.assertEqual(arrivees[:3], [123, 213, 303])

    def test_timers_de_drake(self):
        suivi = Suivi(REGLAGES)
        self.assertEqual(suivi.prochain_drake, 300)
        suivi.maj(depuis_json(simulateur.partie(400)))
        self.assertEqual(suivi.prochain_drake, 372 + 300)
        self.assertEqual(suivi.drakes, {"ORDER": 0, "CHAOS": 1})

    def test_elder_apres_le_quatrieme_drake(self):
        brut = simulateur.partie(100)
        brut["events"]["Events"] = [
            {"EventID": i, "EventName": "DragonKill", "EventTime": 300.0 * (i + 1), "DragonType": "Fire",
             "KillerName": "Vi allié", "Assisters": []}
            for i in range(4)
        ]
        suivi = Suivi(REGLAGES)
        suivi.maj(depuis_json(brut))
        self.assertTrue(suivi.elder)
        self.assertEqual(suivi.prochain_drake, 1200 + 360)

    def test_duree_parlee(self):
        self.assertEqual(duree(30), "30 secondes")
        self.assertEqual(duree(60), "une minute")
        self.assertEqual(duree(90), "une minute 30")
        self.assertEqual(duree(840), "14 minutes")


class PartieSimulee(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conseils = jouer()
        cls.heures = {c.cle: t for t, c in reversed(cls.conseils)}  # première occurrence de chaque clé

    def test_les_moments_cles_sont_vus_au_bon_moment(self):
        attendus = {
            "debut": 0, "niveau-eux-2": 95, "gank-niveau-3": 120, "jungler-vu-200": 200,
            "drake-300-60": 240, "drake-300-30": 270, "grubs": 420, "jungler-6": 500,
            "tour-bot-prise": 700, "mort-or-1": 760, "fin-de-lane": 840, "herald": 840,
            "avantage": 1100, "baron-1200-60": 1140, "baron-1200-30": 1170,
        }
        for cle, heure in attendus.items():
            self.assertEqual(self.heures.get(cle), heure, cle)

    def test_ordre_des_annonces_d_or(self):
        self.assertLess(self.heures["or-1"], self.heures["pv-bas"])
        self.assertIn("items-retard-2", self.heures)
        self.assertIn("farm-6", self.heures)

    def test_un_conseil_n_est_dit_qu_une_fois(self):
        cles = [c.cle for _, c in self.conseils if c.repeter_apres is None]
        self.assertEqual(len(cles), len(set(cles)))

    def test_pas_de_conseil_de_back_a_la_fontaine(self):
        # Achats à 6:40 et 13:15 ; réapparition à 13:05.
        for t, c in self.conseils:
            if c.cle.startswith(("or-", "canon-")):
                self.assertFalse(400 <= t < 420 or 785 <= t < 815, f"{c.cle} à {t}")

    def test_rappel_de_pink_apres_un_achat_sans_pink(self):
        self.assertEqual(self.heures["pink-2"], 406)

    def test_le_coach_ne_noie_pas_le_joueur(self):
        par_minute = len(self.conseils) / (simulateur.FIN / 60)
        self.assertLess(par_minute, 3)

    def test_connexion_en_cours_de_partie(self):
        conseils = jouer(debut=800, fin=830)
        cles = [c.cle for _, c in conseils]
        self.assertIn("debut", cles)
        self.assertEqual(conseils[0][1].fait, "Coach connecté.")
        self.assertNotIn("tour-bot-prise", cles)  # la tour est tombée avant qu'on arrive


class Niveaux(unittest.TestCase):
    def test_ce_qui_est_dit_selon_le_niveau(self):
        c = Conseil("x", 2, "1300 gold.", "Crash ta vague et back.")
        self.assertEqual(c.texte("coach"), "1300 gold. Crash ta vague et back.")
        self.assertEqual(c.texte("faits"), "1300 gold.")
        self.assertEqual(c.texte("silencieux"), "")

    def test_une_conclusion_pure_ne_sort_pas_en_mode_faits(self):
        c = Conseil("x", 2, "", "Premier gank possible.")
        self.assertEqual(c.texte("faits"), "")
        self.assertEqual(c.texte("coach"), "Premier gank possible.")

    def test_niveau_inconnu_refuse(self):
        with tempfile.TemporaryDirectory() as dossier:
            racine = Path(dossier)
            (racine / "donnees").mkdir()
            (racine / "donnees" / "saison.toml").write_bytes((RACINE / "donnees" / "saison.toml").read_bytes())
            (racine / "config.toml").write_text('niveau = "triche"', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "niveau"):
                charger(racine)


class Fichiers(unittest.TestCase):
    def test_une_partie_enregistree_se_relit_a_l_identique(self):
        with tempfile.TemporaryDirectory() as dossier:
            enregistreur = Enregistreur(Path(dossier), "Jinx")
            instants = range(0, 900, 37)
            for t in instants:
                enregistreur.ecrire(simulateur.partie(t))
            enregistreur.fermer()
            relus = [depuis_json(brut) for brut in relire(enregistreur.chemin)]
        self.assertEqual(relus, [depuis_json(simulateur.partie(t)) for t in instants])

    def test_debrief(self):
        with tempfile.TemporaryDirectory() as dossier:
            enregistreur = Enregistreur(Path(dossier), "Jinx")
            for t in range(0, int(simulateur.FIN) + 1):
                enregistreur.ecrire(simulateur.partie(t))
            enregistreur.fermer()
            html = generer(enregistreur.chemin, REGLAGES, Path(dossier)).read_text(encoding="utf-8")
        self.assertIn("Jinx contre Caitlyn et Leona", html)
        self.assertIn("À travailler", html)
        self.assertIn("Tué par Lee Sin avec Caitlyn, Leona", html)
        self.assertIn("Drake dans une minute.", html)

    def test_debrief_d_une_partie_trop_courte(self):
        with tempfile.TemporaryDirectory() as dossier:
            enregistreur = Enregistreur(Path(dossier), "Jinx")
            for t in range(0, 60):
                enregistreur.ecrire(simulateur.partie(t))
            enregistreur.fermer()
            html = generer(enregistreur.chemin, REGLAGES, Path(dossier)).read_text(encoding="utf-8")
        self.assertIn("Partie trop courte", html)


class Reseau(unittest.TestCase):
    def test_le_client_ne_sort_pas_de_la_machine(self):
        with self.assertRaises(ValueError):
            Client("https://example.com")

    def test_pas_de_partie(self):
        self.assertIsNone(Client("http://127.0.0.1:9").lire())

    def test_lecture_du_simulateur(self):
        serveur = simulateur.Serveur(vitesse=1, port=0, depart=300)
        serveur.demarrer()
        try:
            etat = depuis_json(Client(serveur.url).lire())
        finally:
            serveur.arreter()
        self.assertEqual(etat.moi.champion, "Jinx")
        self.assertGreaterEqual(etat.t, 300)


class EnDirect(unittest.TestCase):
    def test_parties_hors_profil(self):
        brut = simulateur.partie(300)
        self.assertIsNone(_hors_profil(depuis_json(brut)))
        brut["gameData"]["gameMode"] = "ARAM"
        self.assertIn("ARAM", _hors_profil(depuis_json(brut)))
        brut["gameData"]["gameMode"] = "CLASSIC"
        brut["allPlayers"][0]["position"] = "TOP"
        self.assertIn("TOP", _hors_profil(depuis_json(brut)))
        brut["allPlayers"][0]["position"] = ""
        self.assertIsNone(_hors_profil(depuis_json(brut)))

    def test_arret_en_pleine_partie(self):
        serveur = simulateur.Serveur(vitesse=200, port=0)
        serveur.demarrer()
        with tempfile.TemporaryDirectory() as dossier, contextlib.redirect_stdout(io.StringIO()) as console:
            coach = Coach(Client(serveur.url), REGLAGES, None, None, 0.005, une_partie=False, dossier=Path(dossier))
            fil = threading.Thread(target=coach.tourner)
            fil.start()
            time.sleep(1.5)
            coach.arreter()
            fil.join(timeout=10)
            serveur.arreter()
            self.assertFalse(fil.is_alive())
            self.assertIn("Partie détectée : Jinx", console.getvalue())
            self.assertTrue(coach.rapport.exists())
            enregistrement = next((Path(dossier) / "parties").glob("*.jsonl.gz"))
            self.assertGreater(len(list(relire(enregistrement))), 10)


if __name__ == "__main__":
    unittest.main()
