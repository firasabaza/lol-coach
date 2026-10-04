"""Tests du coach sur la partie simulée. Lancer : python -m unittest discover -s tests"""

from __future__ import annotations

import contextlib
import ctypes
import importlib.util
import io
import tempfile
import threading
import time
import unittest
from dataclasses import replace
from pathlib import Path

from lolcoach import simulateur
from lolcoach.__main__ import Coach, _hors_profil, a_dire
from lolcoach.client import Client
from lolcoach.compo import adaptations, bottes, chemin, lire_compo, reste_a_payer
from lolcoach.datadragon import objets
from lolcoach.debrief import generer
from lolcoach.enregistreur import Enregistreur, relire
from lolcoach.etat import depuis_json
from lolcoach.moteur import Moteur
from lolcoach.reglages import RACINE, charger
from lolcoach.regles import Conseil, accompli, duree, or_en_poche
from lolcoach.suivi import Suivi, lire_structure, vagues_canon_bot

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
            "debut": 0, "niveau-eux-2": 95, "gank-niveau-3": 120, "jungler-vu-top": 200,
            "jungler-fenetre-200": 230, "jungler-vu-bot": 372,
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
        self.assertEqual(self.heures["pink"], 406)

    def test_mort_du_duo_adverse_dite_une_fois(self):
        # Caitlyn meurt à 9:16, Leona à 9:18 : une annonce pour elle, une pour le duo, puis plus rien.
        cles = [c.cle for _, c in self.conseils if c.cle.startswith("duo-mort") and 540 <= self.heures[c.cle] <= 600]
        self.assertEqual(len(cles), 2)

    def test_le_coach_ne_noie_pas_le_joueur(self):
        par_minute = len(self.conseils) / (simulateur.FIN / 60)
        self.assertLess(par_minute, 3.5)

    def test_connexion_en_cours_de_partie(self):
        conseils = jouer(debut=800, fin=830)
        cles = [c.cle for _, c in conseils]
        self.assertIn("debut", cles)
        self.assertEqual(conseils[0][1].fait, "Coach connecté.")
        self.assertNotIn("tour-bot-prise", cles)  # la tour est tombée avant qu'on arrive


def partie_contre(*champions: str, t: int = 100) -> dict:
    """La partie simulée, avec d'autres champions en face (noms internes, dans l'ordre du tableau)."""
    brut = simulateur.partie(t)
    ennemis = [j for j in brut["allPlayers"] if j["team"] == "CHAOS"]
    for joueur, champion in zip(ennemis, champions):
        joueur["championName"] = champion
        joueur["rawChampionName"] = f"game_character_displayname_{champion}"
    return brut


class Compositions(unittest.TestCase):
    """Ce que les champions de la partie changent : compo adverse, build, objets d'adaptation."""

    def test_lecture_de_la_compo(self):
        # En face dans la partie simulée : Caitlyn, Leona, Lee Sin, Syndra, Darius.
        compo = lire_compo(depuis_json(simulateur.partie(100)))
        self.assertEqual({j.champion for j in compo.ap}, {"Syndra"})
        self.assertEqual(len(compo.ad), 4)
        self.assertEqual({j.champion for j in compo.tanks}, {"Leona", "Darius"})
        self.assertEqual({j.champion for j in compo.plongeurs}, {"Lee Sin"})
        self.assertIn("Leona", {j.champion for j in compo.ultis_engage})

    def test_chemin_type_et_reste_a_payer(self):
        etat = depuis_json(simulateur.partie(100))
        self.assertEqual(chemin(etat.moi), [3032, 3031, 3046])  # Jinx : famille crit
        table = objets()
        recette = table[6672]["recette"]
        composants = sum(table[c]["prix"] for c in recette)
        self.assertEqual(reste_a_payer(6672, []), table[6672]["prix"])
        self.assertEqual(reste_a_payer(6672, recette), table[6672]["prix"] - composants)
        self.assertEqual(reste_a_payer(6672, [6672]), 0)

    def test_adaptations_selon_la_compo(self):
        self.assertEqual(adaptations(depuis_json(simulateur.partie(100)))[0][0], 3036)  # deux tanks : Dominik
        contre_suppression = depuis_json(partie_contre("Caitlyn", "Soraka", "Warwick", "Malzahar", "Aatrox"))
        proposes = [objet for objet, _ in adaptations(contre_suppression)]
        self.assertEqual(proposes[:2], [3140, 3123])  # Ceinture de mercure, puis anti-soin
        self.assertIsNone(bottes(depuis_json(partie_contre("Caitlyn", "Soraka", "Karthus", "Syndra", "Malphite"))))
        plein_de_controles = depuis_json(partie_contre("Ashe", "Leona", "Amumu", "Lissandra", "Maokai"))
        self.assertEqual(bottes(plein_de_controles)[0], 3111)  # Sandales de Mercure

    def test_conseils_avances_sur_la_partie_simulee(self):
        conseils = jouer()
        heures = {c.cle: t for t, c in reversed(conseils)}
        attendus = {"plan-de-lane": 8, "build-type": 25, "build-adaptation": 45, "jungler-precoce": 95,
                    "ulti-Leona ennemie": 470, "etat-10": 635, "plan-de-combat": 1080}
        for cle, heure in attendus.items():
            self.assertEqual(heures.get(cle), heure, cle)
        self.assertIn("finir-3032", heures)  # assez d'or pour finir le premier objet du chemin
        plan = next(c for _, c in conseils if c.cle == "plan-de-lane")
        self.assertIn("Leona engage au contact", plan.action)
        self.assertEqual(plan.texte("faits"), "")  # un plan est une conclusion : rien en mode faits

    def test_baron_pris_par_l_adversaire(self):
        moteur = Moteur(REGLAGES)
        moteur.lire(depuis_json(simulateur.partie(1250)))
        brut = simulateur.partie(1251)
        brut["events"]["Events"].append({"EventID": 99, "EventName": "BaronKill", "EventTime": 1251.0,
                                         "KillerName": "Lee Sin ennemi", "Assisters": [], "Stolen": "False"})
        dits = {c.cle: c for c in moteur.lire(depuis_json(brut))}
        self.assertEqual(dits["baron-pris-99"].fait, "Baron pour eux.")
        self.assertEqual(moteur.suivi.prochain_baron, 1251 + 360)

    @unittest.skipUnless(importlib.util.find_spec("PySide6"), "messagerie en jeu non installée")
    def test_famille_des_bulles(self):
        from lolcoach.fenetre import genre

        self.assertEqual(genre("drake-300-60"), "objectif")
        self.assertEqual(genre("finir-3032"), "or")
        self.assertEqual(genre("menace-Zed"), "danger")
        self.assertEqual(genre("sort-note-Leona-Flash-600"), "sort")
        self.assertEqual(genre("jungler-vu-top"), "jungler")
        self.assertEqual(genre("debut"), "info")


class LectureAdverse(unittest.TestCase):
    """Ce que le coach tire des choix et des achats de l'équipe d'en face."""

    def test_sort_cle_runes_et_sorts_d_invocateur(self):
        moteur = Moteur(REGLAGES)
        moteur.lire(depuis_json(simulateur.partie(59)))
        dit = next(c for c in moteur.lire(depuis_json(simulateur.partie(60))) if c.cle == "lecture-adverse")
        self.assertIn("Lame du zénith de Leona : 12 secondes de recharge", dit.action)
        self.assertIn("Caitlyn joue Jeu de jambes", dit.action)
        self.assertEqual(dit.texte("faits"), "")

    def test_objet_defensif_achete_en_face(self):
        moteur = Moteur(REGLAGES)
        moteur.lire(depuis_json(simulateur.partie(899)))
        brut = simulateur.partie(900)
        syndra = next(j for j in brut["allPlayers"] if j["championName"] == "Syndra")
        syndra["items"].append({"itemID": 3157, "displayName": "Sablier de Zhonya", "price": 0, "count": 1})
        dits = {c.cle: c for c in moteur.lire(depuis_json(brut))}
        self.assertEqual(dits["objet-Syndra ennemie-3157"].fait, "Syndra a son Sablier de Zhonya.")
        self.assertNotIn("objet-Syndra ennemie-3157", {c.cle for c in moteur.lire(depuis_json(brut))})  # dit une fois

    def test_ace_et_inhibiteur(self):
        moteur = Moteur(REGLAGES)
        moteur.lire(depuis_json(simulateur.partie(1250)))
        brut = simulateur.partie(1251)
        brut["events"]["Events"] += [
            {"EventID": 90, "EventName": "Ace", "EventTime": 1251.0, "Acer": "Joueur", "AcingTeam": "ORDER"},
            {"EventID": 91, "EventName": "InhibKilled", "EventTime": 1251.0, "InhibKilled": "Barracks_T2_R1",
             "KillerName": "Lee Sin ennemi", "Assisters": []},
        ]
        dits = {c.cle: c for c in moteur.lire(depuis_json(brut))}
        self.assertEqual((dits["ace-90"].fait, dits["ace-90"].action), ("Ace pour vous.", "Baron tout de suite, puis siège."))
        self.assertEqual(dits["inhibiteur-91"].fait, "Inhibiteur perdu.")

    def test_deux_niveaux_de_retard(self):
        brut = simulateur.partie(300)
        next(j for j in brut["allPlayers"] if j["championName"] == "Caitlyn")["level"] = 7
        cles = [c.cle for c in Moteur(REGLAGES).lire(depuis_json(brut))]
        self.assertIn("debut", cles)  # connexion en cours de partie : seul l'accueil est dit
        moteur = Moteur(REGLAGES)
        moteur.lire(depuis_json(simulateur.partie(299)))
        self.assertIn("niveaux-retard", [c.cle for c in moteur.lire(depuis_json(brut))])


class VraiePartie(unittest.TestCase):
    """Ce que la première vraie partie (outil d'entraînement, patch 26.19) a appris sur l'API du jeu."""

    def test_noms_de_tours(self):
        self.assertEqual(lire_structure("Turret_TChaos_L0_P3_511845594_0"), ("CHAOS", "bot", True))
        self.assertEqual(lire_structure("Turret_TOrder_L2_P2_1526764315_0"), ("ORDER", "top", False))
        self.assertEqual(lire_structure("Turret_TOrder_L1_P3_1242677625_0"), ("ORDER", "mid", True))
        # Le format de la documentation de Riot reste compris.
        self.assertEqual(lire_structure("Turret_T2_R_03_A"), ("CHAOS", "bot", True))
        self.assertEqual(lire_structure("Barracks_T2_R1"), ("CHAOS", "bot", False))
        self.assertIsNone(lire_structure("Minion_T100L0S1N0001"))

    def test_bots_nommes_autrement_dans_les_evenements(self):
        brut = simulateur.partie(100)
        lee = next(j for j in brut["allPlayers"] if j["championName"] == "Lee Sin")
        lee.update(riotId="LeeSin#BOT", riotIdGameName="LeeSin", summonerName="Bot Lee Sin")
        brut["events"]["Events"] = [
            {"EventID": 0, "EventName": "HordeKill", "EventTime": 90.0, "KillerName": "Bot Lee Sin", "Assisters": []}
        ]
        etat = depuis_json(brut)
        self.assertEqual(etat.evenements[0].tueur, etat.jungler_ennemi.nom)
        suivi = Suivi(REGLAGES)
        suivi.maj(etat)
        self.assertEqual(suivi.jungler_vu, (90, "top", "objectif"))  # un grub : il est en haut

    def test_sbires_arrondis_a_la_dizaine(self):
        suivi = Suivi(REGLAGES)
        for t in range(60, 400):
            suivi.maj(depuis_json(simulateur.partie(t)))
        sbires, heure = suivi.cs_palier
        self.assertEqual(sbires % 10, 0)
        self.assertAlmostEqual(suivi.cs_par_minute(depuis_json(simulateur.partie(400))), sbires / (heure / 60))

    def test_prix_total_et_non_cout_de_combinaison(self):
        brut = simulateur.partie(100)
        brut["allPlayers"][0]["items"] = [{"itemID": 6672, "displayName": "Tueur de krakens", "price": 325, "count": 1}]
        self.assertGreaterEqual(depuis_json(brut).moi.valeur_objets, 2500)

    def test_build_complet(self):
        brut = simulateur.partie(1000)
        finis = (6672, 3124, 3115, 3089, 4645, 3157)
        brut["allPlayers"][0]["items"] = [
            *({"itemID": i, "displayName": "objet fini", "price": 300, "count": 1} for i in finis),
            {"itemID": 3340, "displayName": "Balise camouflée", "price": 0, "count": 1},
        ]
        brut["activePlayer"]["currentGold"] = 5000.0
        etat = depuis_json(brut)
        self.assertTrue(etat.moi.build_complet)
        self.assertFalse(etat.moi.place_libre)
        self.assertEqual(or_en_poche(etat), 0)

        moteur = Moteur(REGLAGES)
        moteur.lire(depuis_json(simulateur.partie(999)))
        cles = [c.cle for c in moteur.lire(etat)]
        self.assertIn("build-complet", cles)
        self.assertEqual([c for c in cles if c.startswith(("or-", "canon-", "pink"))], [])

    def test_conseil_accompli(self):
        suivi = Suivi(REGLAGES)
        avant = depuis_json(simulateur.partie(380))
        suivi.maj(avant)
        back = Conseil("or-1", 2, "1700 gold.", "Crash ta vague et back.")
        self.assertFalse(accompli(back, 380, avant, suivi))
        apres = depuis_json(simulateur.partie(401))  # il vient d'acheter
        suivi.maj(apres)
        self.assertTrue(accompli(back, 380, apres, suivi))
        self.assertFalse(accompli(Conseil("drake-300-60", 2, "Drake dans une minute.", ""), 380, apres, suivi))


class JunglerAdverse(unittest.TestCase):
    """Chaque indice de position donné par le jeu : kill, objectif, tour, réapparition."""

    def lieu_apres(self, evenement: dict) -> tuple[float, str, str] | None:
        brut = simulateur.partie(100)
        brut["events"]["Events"] = [{"EventID": 0, "EventTime": 90.0, **evenement}]
        suivi = Suivi(REGLAGES)
        suivi.maj(depuis_json(brut))
        return suivi.jungler_vu

    def test_objectifs_et_tours(self):
        lee = "Lee Sin ennemi"
        self.assertEqual(self.lieu_apres({"EventName": "DragonKill", "KillerName": lee}), (90, "bot", "objectif"))
        self.assertEqual(self.lieu_apres({"EventName": "HeraldKill", "KillerName": lee}), (90, "top", "objectif"))
        self.assertEqual(
            self.lieu_apres({"EventName": "TurretKilled", "TurretKilled": "Turret_T1_L_03_A", "KillerName": lee}),
            (90, "top", "tour"),
        )
        self.assertEqual(
            self.lieu_apres({"EventName": "InhibKilled", "InhibKilled": "Barracks_T1_C1", "Assisters": [lee]}),
            (90, "mid", "tour"),
        )
        self.assertIsNone(self.lieu_apres({"EventName": "DragonKill", "KillerName": "Vi allié"}))

    def test_kill_place_le_jungler_la_ou_joue_la_victime(self):
        kill = {"EventName": "ChampionKill", "KillerName": "Lee Sin ennemi", "VictimName": "Ahri allié"}
        self.assertEqual(self.lieu_apres(kill), (90, "mid", "kill"))

    def test_retour_en_jeu_apres_une_mort(self):
        moteur = Moteur(REGLAGES)
        dits = []
        for t, mort in ((300, False), (301, True), (302, True), (303, False)):
            brut = simulateur.partie(t)
            lee = next(j for j in brut["allPlayers"] if j["championName"] == "Lee Sin")
            lee["isDead"], lee["respawnTimer"] = mort, 20.0 if mort else 0.0
            dits += [c.cle for c in moteur.lire(depuis_json(brut))]
        self.assertEqual(moteur.suivi.jungler_vu, (303, "base", "retour"))
        self.assertIn("jungler-mort-0", dits)
        self.assertIn("jungler-vu-base", dits)


class SortsEnnemis(unittest.TestCase):
    """Minuteurs des sorts d'invocateur que le joueur signale lui-même."""

    def setUp(self):
        self.moteur = Moteur(REGLAGES)
        self.moteur.lire(depuis_json(simulateur.partie(599)))

    def lire(self, t: int, brut: dict | None = None) -> list[str]:
        return [c.texte("coach") for c in self.moteur.lire(depuis_json(brut or simulateur.partie(t)))]

    def test_flash_du_support(self):
        self.moteur.suivi.noter_sort(depuis_json(simulateur.partie(600)), 5, "flash")
        self.assertIn(
            "Flash de Leona noté, retour à 15 minutes. "
            "Pas de Flash pendant 5 minutes : c'est la fenêtre pour l'attraper.",
            self.lire(600),
        )
        self.assertEqual(self.moteur.suivi.sorts[("Leona ennemie", "SummonerFlash")].retour, 900)
        self.assertIn("Flash de Leona dans 30 secondes. Dernière fenêtre pour l'attraper.", self.lire(870))
        self.assertIn("Flash de Leona de nouveau disponible.", self.lire(900))
        self.lire(906)
        self.assertEqual(self.moteur.suivi.sorts, {})

    def test_autre_sort_et_ordre_du_tableau(self):
        etat = depuis_json(simulateur.partie(600))
        self.moteur.suivi.noter_sort(etat, 4, "autre")
        self.assertIn("Ignite de Caitlyn noté, retour à 13 minutes.", self.lire(600))
        self.assertEqual([etat.ennemi_numero(n).champion for n in range(1, 6)],
                         ["Darius", "Lee Sin", "Syndra", "Caitlyn", "Leona"])

    def test_bottes_de_lucidite(self):
        brut = simulateur.partie(600)
        leona = next(j for j in brut["allPlayers"] if j["championName"] == "Leona")
        leona["items"].append({"itemID": 3158, "displayName": "Bottes de lucidité ionienne", "price": 900, "count": 1})
        self.moteur.suivi.noter_sort(depuis_json(brut), 5, "flash")
        retour = self.moteur.suivi.sorts[("Leona ennemie", "SummonerFlash")].retour
        self.assertAlmostEqual(retour, 600 + 300 * 100 / 110)

    def test_arbre_inspiration_suppose_perspicacite_cosmique(self):
        brut = simulateur.partie(600)
        leona = next(j for j in brut["allPlayers"] if j["championName"] == "Leona")
        leona["runes"] = {"keystone": {"id": 8439}, "primaryRuneTree": {"id": 8400}, "secondaryRuneTree": {"id": 8300}}
        self.moteur.suivi.noter_sort(depuis_json(brut), 5, "flash")
        minuteur = self.moteur.suivi.sorts[("Leona ennemie", "SummonerFlash")]
        self.assertAlmostEqual(minuteur.retour, 600 + 300 * 100 / 118)
        self.assertTrue(any("Flash de Leona noté, retour au plus tôt à 14 minutes 14." in dit for dit in self.lire(600)))

    def test_double_appui_annule(self):
        self.moteur.suivi.noter_sort(depuis_json(simulateur.partie(600)), 5, "flash")
        self.lire(600)
        self.moteur.suivi.noter_sort(depuis_json(simulateur.partie(604)), 5, "flash")
        self.assertIn("Flash de Leona : minuteur annulé.", self.lire(604))
        self.assertEqual(self.moteur.suivi.sorts, {})

    def test_pas_de_minuteur_pour_le_smite(self):
        self.moteur.suivi.noter_sort(depuis_json(simulateur.partie(600)), 2, "autre")
        self.assertIn("Pas de minuteur pour Smite.", self.lire(600))
        self.moteur.suivi.noter_sort(depuis_json(simulateur.partie(601)), 9, "flash")
        self.assertIn("Pas d'ennemi numéro 9.", self.lire(601))

    def test_raccourcis(self):
        from lolcoach.touches import Touches, lire_raccourci

        self.assertEqual(lire_raccourci("ctrl+f1"), (0x4002, 0x70))
        self.assertEqual(lire_raccourci("Shift + F5"), (0x4004, 0x74))
        self.assertEqual(lire_raccourci("alt+num5"), (0x4001, 0x65))
        with self.assertRaises(ValueError):
            lire_raccourci("ctrl+espace")

        touches = Touches({"flash": ["ctrl+alt+shift+f13", "ctrl+alt+shift+f14"], "autre": ["ctrl+alt+shift+f15"]})
        self.assertEqual(touches.activer(), [])  # Windows accepte les trois raccourcis
        # Ce que Windows envoie quand le raccourci numéro 1 puis le numéro 2 sont pressés.
        for numero in (1, 2):
            ctypes.windll.user32.PostThreadMessageW(touches._fil, 0x0312, numero, 0)
        touches.desactiver()
        self.assertEqual(touches.appuis(), [(2, "flash"), (1, "autre")])


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


class VoixCoupee(unittest.TestCase):
    """Certains conseils restent affichés mais ne sont plus dits : pinks, back sous un seuil d'or."""

    VOIX = {"dire_pinks": False, "dire_back_des": 2000}

    def etat(self, or_: float):
        brut = simulateur.partie(600)
        brut["activePlayer"]["currentGold"] = or_
        return depuis_json(brut)

    def test_pink_jamais_dite(self):
        self.assertFalse(a_dire(Conseil("pink", 3, "Pas de pink dans ton inventaire.", ""), self.etat(3000), self.VOIX))

    def test_back_sur_l_or_dit_seulement_a_partir_du_seuil(self):
        for cle in ("or-2", "canon-2", "finir-6672", "drake-672-reset"):
            conseil = Conseil(cle, 2, "1300 gold.", "Crash ta vague et back.")
            self.assertFalse(a_dire(conseil, self.etat(1300), self.VOIX), cle)
            self.assertTrue(a_dire(conseil, self.etat(2000), self.VOIX), cle)
        dormant = Conseil("or-dormant-2", 2, "2050 gold non dépensés.", "Reset maintenant.")
        self.assertTrue(a_dire(dormant, self.etat(2050), self.VOIX))

    def test_le_reste_est_toujours_dit(self):
        for cle in ("drake-300-60", "pv-bas", "jungler-vu-top", "menace-Zed", "vision"):
            self.assertTrue(a_dire(Conseil(cle, 2, "x", "y"), self.etat(500), self.VOIX), cle)

    def test_sans_reglage_rien_n_est_coupe(self):
        self.assertTrue(a_dire(Conseil("pink", 3, "x", ""), self.etat(0), {}))
        self.assertTrue(a_dire(Conseil("or-1", 2, "x", "y"), self.etat(1300), {}))


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
