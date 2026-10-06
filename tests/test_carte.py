"""Tests de la décision après un combat gagné, du placement sur la carte et de l'arbitre par état.

Lancer : python -m unittest discover -s tests
"""

from __future__ import annotations

import contextlib
import ctypes
import io
import unittest
from dataclasses import replace

from lolcoach import regles, simulateur, strategie
from lolcoach.__main__ import Coach
from lolcoach.carte import apres_combat, directions, tour_a_prendre
from lolcoach.client import Client
from lolcoach.etat import depuis_json
from lolcoach.moteur import Moteur
from lolcoach.rapport import drake_jouable, peut_presser
from lolcoach.reglages import charger
from lolcoach.regles import INFO, TEMPO, URGENT, Conseil
from lolcoach.suivi import Suivi, rang_tour

REGLAGES = replace(charger(), niveau="coach")


def partie(t: int, pv: float | None = None, poche: float | None = None, retour: float | None = None,
           tours: tuple[str, ...] = (), drake_pris_a: float | None = None) -> dict:
    """La partie simulée à l'instant t, avec les PV, l'or, les tours tombées ou les retours qu'on veut."""
    brut = simulateur.partie(t)
    if pv is not None:
        brut["activePlayer"]["championStats"]["currentHealth"] = 1800.0 * pv
    if poche is not None:
        brut["activePlayer"]["currentGold"] = poche
    if retour is not None:
        for joueur in brut["allPlayers"]:
            if joueur["isDead"] and joueur["team"] == "CHAOS":
                joueur["respawnTimer"] = retour
    evenements = brut["events"]["Events"]
    for nom in tours:
        evenements.append({"EventID": len(evenements), "EventName": "TurretKilled", "EventTime": t - 60.0,
                           "TurretKilled": nom, "KillerName": "Minion", "Assisters": []})
    if drake_pris_a is not None:
        evenements.append({"EventID": len(evenements), "EventName": "DragonKill", "EventTime": drake_pris_a,
                           "DragonType": "Air", "Stolen": "False", "KillerName": "Vi allié", "Assisters": []})
    return brut


def lire(brut: dict) -> tuple:
    etat = depuis_json(brut)
    suivi = Suivi(REGLAGES)
    suivi.maj(etat)
    return etat, suivi


class ApresUnCombat(unittest.TestCase):
    """À 18:20 dans la partie simulée, trois ennemis sont morts pour 34 secondes et le drake est là."""

    def decision(self, **etat):
        e, s = lire(partie(1100, **etat))
        return apres_combat(e, s, REGLAGES)

    def test_en_forme_le_drake(self):
        self.assertEqual(self.decision(), apres_combat(*lire(partie(1100)), REGLAGES))
        self.assertEqual((self.decision().quoi, self.decision().phrase), ("objectif", "Drake, maintenant."))

    def test_bas_en_pv_on_rentre_meme_avec_le_drake_disponible(self):
        d = self.decision(pv=0.33, poche=1400)
        self.assertEqual(d.quoi, "back")
        self.assertIn("Tu es à 33 %", d.phrase)
        self.assertIn("Back maintenant. À la boutique : ", d.phrase)

    def test_sans_objectif_la_tour_est_nommee(self):
        d = self.decision(drake_pris_a=1090.0)
        self.assertEqual(d.quoi, "tour")
        # Une tour extérieure se prend en plusieurs passages : elle durcit après chaque plaque.
        self.assertEqual(d.phrase, "La tour mid extérieure, avec la vague. Une ou deux plaques à 120 gold, pas plus : "
                                   "elle durcit après chacune.")
        # La tour mid déjà tombée : la suivante sur la même lane. De l'or en poche : le back vient après.
        d = self.decision(drake_pris_a=1090.0, tours=("Turret_TChaos_L1_P3_1", ), poche=1500)
        self.assertEqual(d.phrase, "La tour mid intérieure, avec la vague. Back juste après : tu as 1500 gold à dépenser.")

    def test_un_inhibiteur_a_decouvert_passe_avant_une_tour(self):
        ouverte = ("Turret_TChaos_L0_P3_1", "Turret_TChaos_L0_P2_1", "Turret_TChaos_L0_P1_1")
        e, s = lire(partie(1100, tours=ouverte))
        self.assertEqual(tour_a_prendre(e, s, REGLAGES), "l'inhibiteur bot")

    def test_de_l_or_et_peu_de_temps_on_rentre(self):
        # Réapparition dans 12 secondes, plus 12 de trajet jusqu'à la lane mid avec le homeguard.
        d = self.decision(drake_pris_a=1090.0, poche=1500, retour=12)
        self.assertEqual(d.quoi, "back")
        self.assertIn("Ils sont de retour en lane dans 24 secondes : pas le temps pour une tour.", d.phrase)

    def test_ils_reviennent_il_n_y_a_plus_rien_a_dire(self):
        self.assertIsNone(self.decision(retour=2))
        cles = [c.cle for c in regles.avantage(*lire(partie(1100, retour=2)), REGLAGES)]
        self.assertNotIn("avantage", cles)

    def test_le_coach_tranche_une_seule_fois(self):
        # Bas en PV depuis 18:10, de quoi acheter, trois morts en face à 18:20 : un seul ordre, rentrer.
        moteur = Moteur(REGLAGES)
        dits = []
        for t in range(0, 1125):
            etat = depuis_json(partie(t, pv=0.30, poche=1400) if t >= 1090 else simulateur.partie(t))
            dits += [(t, c) for c in moteur.lire(etat)]
        tard = [c for t, c in dits if t >= 1095]
        ordre = next(c for c in tard if c.cle == "avantage")
        self.assertEqual(ordre.intention, "back")
        self.assertEqual([c.cle for c in tard if c.intention in ("objectif", "agressif")], [])


class Placement(unittest.TestCase):
    def cles(self, brut: dict) -> list[str]:
        return [d.cle for d in directions(*lire(brut), REGLAGES)]

    def test_en_lane_on_reste_bot(self):
        self.assertEqual(self.cles(simulateur.partie(400)), ["lane", "sous-tour", "plaques-mid"])

    def test_milieu_de_partie_mid_puis_les_replis(self):
        # 16:00, drake pris à l'instant : pas d'objectif avant quatre minutes. Mid d'abord, la side du
        # prochain objectif, puis la jungle.
        e, s = lire(partie(960, drake_pris_a=955.0))
        choix = directions(e, s, REGLAGES)
        self.assertEqual([d.cle for d in choix], ["mid", "vagues", "side", "jungle"])
        self.assertIn("la lane la plus courte", choix[0].phrase)
        self.assertIn("regarde les trois vagues et va à la plus grosse", choix[1].phrase)
        self.assertIn("La vague top quand elle arrive à ta tour extérieure", choix[2].phrase)  # côté Baron

    def test_les_tours_perdues_reculent_la_limite(self):
        perdues = ("Turret_TOrder_L1_P3_1", "Turret_TOrder_L2_P3_1", "Turret_TOrder_L2_P2_1")
        choix = directions(*lire(partie(960, tours=perdues, drake_pris_a=955.0)), REGLAGES)
        self.assertIn("Mid, devant ta tour intérieure", choix[0].phrase)
        self.assertIn("Plus de tour en top : n'y va pas seul.", choix[2].phrase)

    def test_un_objectif_proche_passe_devant(self):
        # 19:15 : Baron dans 45 secondes.
        choix = directions(*lire(partie(1155, drake_pris_a=1150.0)), REGLAGES)
        self.assertEqual(choix[0].cle, "objectif")
        self.assertIn("Baron dans 45 secondes : passe par mid, puis côté top.", choix[0].phrase)

    def test_bas_en_pv_le_back_d_abord(self):
        choix = directions(*lire(partie(960, pv=0.25, poche=900, drake_pris_a=955.0)), REGLAGES)
        self.assertEqual(choix[0].cle, "back")
        self.assertIn("Tu es à 25 % : back d'abord.", choix[0].phrase)

    def test_en_superiorite_la_meme_decision_que_l_avantage(self):
        e, s = lire(partie(1100))
        premier = directions(e, s, REGLAGES)[0]
        self.assertEqual((premier.cle, premier.phrase), ("nombre", "Ils ne sont plus que 2. Drake, maintenant."))

    def test_la_touche_donne_une_reponse_puis_les_suivantes(self):
        moteur = Moteur(REGLAGES)
        reponses = []
        for t in range(0, 1000):
            if t in (960, 964, 968, 995):
                moteur.suivi.demander_direction()
            brut = partie(t, drake_pris_a=955.0) if t >= 955 else simulateur.partie(t)
            reponses += [c.action for c in moteur.lire(depuis_json(brut)) if c.cle.startswith("direction-")]
        self.assertEqual(len(reponses), 4)
        self.assertTrue(reponses[0].startswith("Mid : c'est la lane la plus courte"))
        self.assertTrue(reponses[1].startswith("Sinon : si un allié farme déjà mid, ne partage pas"))
        self.assertTrue(reponses[2].startswith("Sinon : la vague top"))
        self.assertEqual(reponses[3], reponses[0])  # plus de 25 secondes après : on repart de la meilleure réponse

    def test_tours_et_inhibiteurs_suivis_des_deux_cotes(self):
        self.assertEqual([rang_tour(f"Turret_TChaos_L1_P{n}_42_0") for n in (3, 2, 1)], [1, 2, 3])
        self.assertIsNone(rang_tour("Turret_TChaos_C_01_A"))
        brut = partie(1100, tours=("Turret_TOrder_L2_P3_1", "Turret_TChaos_L1_P3_1", "Turret_TChaos_L1_P2_1"))
        evenements = brut["events"]["Events"]
        evenements.append({"EventID": len(evenements), "EventName": "InhibKilled", "EventTime": 1050.0,
                           "InhibKilled": "Barracks_TChaos_L1", "KillerName": "Joueur", "Assisters": []})
        _, s = lire(brut)
        self.assertEqual(s.tours_tombees, {("ORDER", "top"): 1, ("CHAOS", "mid"): 2, ("CHAOS", "bot"): 1})
        self.assertEqual(s.inhibiteurs, {("CHAOS", "mid")})

    def test_une_tour_mid_perdue_deplace_le_joueur(self):
        moteur = Moteur(REGLAGES)
        dits = []
        for t in range(0, 1000):
            brut = simulateur.partie(t)
            if t >= 950:
                evenements = brut["events"]["Events"]
                evenements.append({"EventID": len(evenements), "EventName": "TurretKilled", "EventTime": 950.0,
                                   "TurretKilled": "Turret_TOrder_L1_P3_1", "KillerName": "Syndra ennemie", "Assisters": []})
            dits += moteur.lire(depuis_json(brut))
        perdue = next(c for c in dits if c.cle == "tour-mid-perdue-1")
        self.assertEqual(perdue.fait, "Ta tour mid extérieure est tombée.")
        self.assertIn("devant ta tour intérieure", perdue.action)


class EtatDuJoueur(unittest.TestCase):
    def test_un_drake_ne_se_propose_pas_sans_jungler_ni_en_inferiorite(self):
        brut = simulateur.partie(960)
        self.assertTrue(drake_jouable(depuis_json(brut)))
        jungler = next(j for j in brut["allPlayers"] if j["team"] == "ORDER" and j["position"] == "JUNGLE")
        jungler["isDead"], jungler["respawnTimer"] = True, 30.0
        self.assertFalse(drake_jouable(depuis_json(brut)))

    def test_deux_morts_precoces_la_fenetre_sert_a_farmer(self):
        brut = simulateur.partie(210)
        moi = brut["allPlayers"][0]
        self.assertTrue(peut_presser(depuis_json(brut)))
        moi["scores"].update(kills=0, deaths=2)
        etat = depuis_json(brut)
        self.assertFalse(peut_presser(etat))
        suivi = Suivi(REGLAGES)
        suivi.maj(depuis_json(simulateur.partie(199)))
        suivi.maj(etat)  # le jungler adverse vient de tuer en top
        vu = next(c for c in regles.jungler(etat, suivi, REGLAGES) if c.cle == "jungler-vu-top")
        self.assertIn("farme sans crainte", vu.action)
        self.assertEqual(vu.intention, "")


class Arbitre(unittest.TestCase):
    """Le moteur, avec des règles de test à la place des vraies."""

    def moteur(self, scenario: dict[int, list[Conseil]]) -> Moteur:
        anciennes = regles.REGLES, strategie.REGLES
        self.addCleanup(lambda: (setattr(regles, "REGLES", anciennes[0]), setattr(strategie, "REGLES", anciennes[1])))
        regles.REGLES = (lambda e, s, c: iter(scenario.get(int(e.t), [])),)
        strategie.REGLES = ()
        return Moteur(REGLAGES)

    def test_une_consigne_retournee_est_annoncee(self):
        moteur = self.moteur({
            10: [Conseil("back", TEMPO, "1300 gold.", "Reset.", intention="back")],
            20: [Conseil("drake", TEMPO, "Leur jungler est mort.", "Drake gratuit.", intention="objectif")],
        })
        dits = [c for t in range(1, 40) for c in moteur.lire(depuis_json(simulateur.partie(t)))]
        self.assertEqual([c.fait for c in dits], ["1300 gold.", "Le back attendra. Leur jungler est mort."])

    def test_le_moins_important_attend(self):
        moteur = self.moteur({
            10: [Conseil("drake", TEMPO, "Drake.", "", intention="objectif")],
            20: [Conseil("back", TEMPO, "1300 gold.", "Reset.", intention="back")],
        })
        self.assertEqual([c.cle for t in range(1, 40) for c in moteur.lire(depuis_json(simulateur.partie(t)))], ["drake"])

    def test_l_urgence_se_decide_sur_l_etat_du_moment(self):
        # « Recule » dit à l'instant ne retient pas un ordre urgent, et l'ordre dit qu'il change le plan.
        moteur = self.moteur({
            10: [Conseil("alerte", TEMPO, "Deux alliés morts.", "Recule.", intention="danger")],
            20: [Conseil("avantage", URGENT, "3 ennemis morts.", "Drake, maintenant.", intention="objectif")],
        })
        dits = [c for t in range(1, 40) for c in moteur.lire(depuis_json(simulateur.partie(t)))]
        self.assertEqual(dits[-1].fait, "Changement de plan. 3 ennemis morts.")

    def test_bas_en_pv_on_n_envoie_pas_le_joueur_se_battre(self):
        scenario = {t: [Conseil("force", TEMPO, "Tu es devant.", "Force le trade.", intention="agressif"),
                        Conseil("info", INFO, "Drake dans une minute.", "")] for t in (340, 360)}
        moteur = self.moteur(scenario)
        dits = []
        for t in range(300, 420):  # dans la partie simulée, le joueur est à 30 % de 5:30 à 6:35 puis soigné
            dits += [(t, c.cle) for c in moteur.lire(depuis_json(partie(t, pv=0.30 if t < 350 else 0.9)))]
        self.assertEqual(dits, [(340, "info"), (360, "force")])


class Commandes(unittest.TestCase):
    def test_la_voix_se_coupe_et_se_remet_en_partie(self):
        class Voix:
            dites: list[str] = []

            def dire(self, texte: str) -> None:
                self.dites.append(texte)

        creees = []
        coach = Coach(Client("http://127.0.0.1:9"), REGLAGES, None, None, 1.0, une_partie=True,
                      creer_voix=lambda: creees.append(Voix()) or creees[-1])
        self.assertFalse(coach.parle)  # coupée au départ
        with contextlib.redirect_stdout(io.StringIO()) as journal:
            coach._basculer_voix()
            self.assertTrue(coach.parle)
            self.assertEqual((len(creees), Voix.dites), (1, ["Voix activée."]))
            coach._basculer_voix()
            self.assertFalse(coach.parle)
            coach._basculer_voix()
        self.assertEqual(len(creees), 1)  # la même voix resservie, pas une deuxième
        self.assertEqual(journal.getvalue().splitlines()[:2], ["Voix activée.", "Voix coupée."])

    def test_sans_voix_possible_la_touche_ne_fait_rien(self):
        coach = Coach(Client("http://127.0.0.1:9"), REGLAGES, None, None, 1.0, une_partie=True)
        coach._basculer_voix()
        self.assertFalse(coach.parle)

    def test_raccourcis_de_commande(self):
        from lolcoach.touches import Touches

        touches = Touches({"flash": ["ctrl+alt+shift+f17"],
                           "commandes": {"direction": "ctrl+alt+shift+f18", "voix": "ctrl+alt+shift+f19"}})
        self.assertEqual(touches.activer(), [])
        for numero in (2, 1, 0):
            ctypes.windll.user32.PostThreadMessageW(touches._fil, 0x0312, numero, 0)
        touches.desactiver()
        self.assertEqual(touches.appuis(), [(0, "voix"), (0, "direction"), (1, "flash")])


if __name__ == "__main__":
    unittest.main()
