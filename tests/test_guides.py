"""Tests de ce que le coach a appris des guides : plan de trade, vague, timers, composants, compos, réglages.

Lancer : python -m unittest discover -s tests
"""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from test_coach import donner, jouer, partie_contre

from lolcoach import regles, reglages_jeu, simulateur, strategie
from lolcoach.achats import a_la_boutique, besoins, bon_back, prochain, tempo_adverse
from lolcoach.etat import depuis_json
from lolcoach.moteur import Moteur
from lolcoach.reglages import charger
from lolcoach.suivi import Suivi

REGLAGES = replace(charger(), niveau="coach")


def moi_sur(brut: dict, nom: str, cle: str) -> dict:
    moi = brut["allPlayers"][0]
    moi["championName"], moi["rawChampionName"] = nom, f"game_character_displayname_{cle}"
    return brut


def suivi_de(etat) -> Suivi:
    suivi = Suivi(REGLAGES)
    suivi.maj(etat)
    return suivi


class Lane(unittest.TestCase):
    def test_le_plan_de_trade_vient_des_deux_runes(self):
        # Jinx en Tempo mortel contre Caitlyn en Jeu de jambes : elle gagne l'échange court, Jinx le combat long.
        etat = depuis_json(simulateur.partie(60))
        (lecture,) = strategie.lecture_adverse(etat, suivi_de(etat), REGLAGES)
        self.assertIn("Tu joues Tempo mortel, Caitlyn joue Jeu de jambes", lecture.action)
        self.assertIn("les échanges courts sont pour Caitlyn, les combats qui durent pour toi", lecture.action)

    def test_la_vague_se_tient_pour_son_support(self):
        etat = depuis_json(simulateur.partie(40))  # Lulu avec toi, Leona en face
        (plan,) = strategie.plan_de_vague(etat, suivi_de(etat), REGLAGES)
        self.assertIn("Avec Lulu : construis une grosse vague", plan.action)
        self.assertIn("Ne tape pas Leona", plan.action)
        brut = simulateur.partie(40)
        allie = next(j for j in brut["allPlayers"] if j["team"] == "ORDER" and j["position"] == "UTILITY")
        allie["championName"], allie["rawChampionName"] = "Nautilus", "game_character_displayname_Nautilus"
        etat = depuis_json(brut)
        (plan,) = strategie.plan_de_vague(etat, suivi_de(etat), REGLAGES)
        self.assertIn("jamais collée à leur tour", plan.action)
        self.assertIn("Reste à portée d'auto de lui", plan.action)

    def test_ward_au_premier_canon_et_retour_du_jungler_a_3_45(self):
        dits = jouer(fin=240)
        heures = {c.cle: t for t, c in reversed(dits)}
        textes = {c.cle: c.action for _, c in dits}
        self.assertEqual(heures["gank-niveau-3"], 145)
        self.assertIn("Le premier canon meurt : ward la rivière maintenant", textes["gank-niveau-3"])

    def test_retour_du_jungler_sur_ses_premiers_camps(self):
        # Lee Sin a tué en haut à 2:40 : il a fini son clear là-haut, donc ses premiers camps sont de ton côté.
        def partie(t: int) -> dict:
            brut = simulateur.partie(t)
            evenements = [ev for ev in brut["events"]["Events"] if ev["EventTime"] != 200.0]
            if t >= 160:
                evenements.append({"EventID": 99, "EventName": "ChampionKill", "EventTime": 160.0,
                                   "KillerName": "Lee Sin ennemi", "VictimName": "Garen allié", "Assisters": []})
            brut["events"]["Events"] = sorted(evenements, key=lambda ev: ev["EventTime"])
            for i, ev in enumerate(brut["events"]["Events"]):
                ev["EventID"] = i
            return brut

        moteur = Moteur(REGLAGES)
        dits = [(t, c) for t in range(0, 245) for c in moteur.lire(depuis_json(partie(t)))]
        heure, retour = next((t, c) for t, c in dits if c.cle == "jungler-respawn")
        self.assertTrue(215 <= heure < 240, heure)  # dans la fenêtre de 3:45, après le « il a eu le temps de descendre »
        self.assertIn("il redescend", retour.action)
        self.assertEqual(retour.intention, "prudent")
        # Vu en haut à l'instant (3:20 dans la partie simulée) : la règle de la fenêtre de 30 secondes suffit.
        self.assertNotIn("jungler-respawn", [c.cle for _, c in jouer(fin=245)])

    def test_un_jungler_qui_ne_passe_pas_par_la_riviere(self):
        etat = depuis_json(partie_contre("Caitlyn", "Leona", "Zac", "Syndra", "Darius", t=150))
        ward = next(c for c in regles.jungler(etat, suivi_de(etat), REGLAGES) if c.cle == "gank-niveau-3")
        self.assertIn("Zac ne passe pas forcément par la rivière", ward.action)

    def test_le_tp_adverse_note_compte_au_drake(self):
        moteur = Moteur(REGLAGES)
        annonce = None
        for t in range(0, 250):
            brut = simulateur.partie(t)
            top = next(j for j in brut["allPlayers"] if j["team"] == "CHAOS" and j["position"] == "TOP")
            top["summonerSpells"]["summonerSpellTwo"] = {
                "displayName": "Téléportation", "rawDisplayName": "GeneratedTip_SummonerSpell_SummonerTeleport_DisplayName"}
            etat = depuis_json(brut)
            if t == 200:
                moteur.suivi.noter_sort(etat, 1, "autre")  # le joueur a vu partir le TP du top adverse
            annonce = next((c for c in moteur.lire(etat) if c.cle == "drake-300-60"), annonce)
        self.assertIn("Le TP de Darius ne revient qu'à 8 minutes 20", annonce.action)


class Achats(unittest.TestCase):
    def test_les_degats_purs_d_abord(self):
        depart = depuis_json(simulateur.partie(100))
        # 700 gold sur un build à BF Glaive : une Épée longue sert à chaque auto, la Fronde seulement si ça dure.
        self.assertEqual(a_la_boutique(depart, 700), "Épée longue, en route vers Flèches des Yun Tal")
        self.assertEqual(bon_back(depart, 1300), 1300)  # le composant qui compte : le BF Glaive
        draven = depuis_json(moi_sur(simulateur.partie(100), "Draven", "Draven"))
        self.assertEqual(bon_back(draven, 1300), 875)  # Percepteur : la Pioche

    def test_le_premier_objet_suit_ce_que_le_joueur_monte(self):
        brut = simulateur.partie(300)
        donner(brut, "BOTTOM", (1055, "Lame de Doran", 450), (1037, "Pioche", 875), moi=True)
        self.assertEqual(prochain(depuis_json(brut)).objet, 2523)  # une Pioche mène aux Lunettes Hextech C44
        donner(brut, "BOTTOM", (1055, "Lame de Doran", 450), (1038, "BF Glaive", 1300), moi=True)
        self.assertEqual(prochain(depuis_json(brut)).objet, 3032)  # un BF Glaive, aux Flèches des Yun Tal

    def test_en_retard_l_objet_de_transition_attend(self):
        objets = ((3508, "Faux spectrale", 3050), (3006, "Jambières du berzerker", 1100))
        brut = moi_sur(partie_contre("Caitlyn", "Lulu", "Karthus", "Syndra", "Malphite", t=1100), "Lucian", "Lucian")
        donner(brut, "BOTTOM", *objets, moi=True)
        self.assertEqual(prochain(depuis_json(brut)).objet, 6675)  # à égalité : Tremblelame navori
        donner(brut, "BOTTOM", (3031, "Lame d'infini", 3500), (3032, "Flèches des Yun Tal", 3000), (3036, "Dominik", 3300))
        vise = prochain(depuis_json(brut))
        self.assertEqual(vise.objet, 3031)  # leur ADC a deux objets d'avance : Lame d'infini d'abord
        self.assertIn("tu es en retard", vise.raison)

    def test_compo_qui_tue_vite_ou_compo_qui_dure(self):
        rush = depuis_json(partie_contre("Caitlyn", "Leona", "Lee Sin", "Zed", "Darius"))
        self.assertEqual(tempo_adverse(rush)[0], "rush")
        self.assertIn("survie_ad", [besoin for besoin, _, _ in besoins(rush)])
        posee = depuis_json(partie_contre("Caitlyn", "Nami", "Lee Sin", "Orianna", "Darius"))
        self.assertEqual(tempo_adverse(posee)[0], "defense")
        self.assertNotIn("survie_ad", [besoin for besoin, _, _ in besoins(posee)])
        self.assertEqual(tempo_adverse(depuis_json(simulateur.partie(100)))[0], "")  # Syndra et Leona : pas tranché


class ReglagesDuJeu(unittest.TestCase):
    def fichier(self, dossier: str, **valeurs: str) -> Path:
        reglages = {"EnableTargetedAttackMove": "1", "ShowAttackRadius": "1", "evtPlayerAttackMove": "[x],[<Unbound>]",
                    "evtPlayerAttackMoveClick": "[<Unbound>]", "evtChampionOnly": "[<Unbound>]", **valeurs}
        sections = {"General": ["EnableTargetedAttackMove"], "HUD": ["ShowAttackRadius"],
                    "GameEvents": ["evtPlayerAttackMove", "evtPlayerAttackMoveClick", "evtChampionOnly"]}
        contenu = {"files": [{"name": "Game.cfg", "sections": [
            {"name": section, "settings": [{"name": nom, "value": reglages[nom]} for nom in noms]}
            for section, noms in sections.items()]}]}
        racine = Path(dossier)
        (racine / "Config").mkdir()
        (racine / "Config" / "PersistedSettings.json").write_text(json.dumps(contenu), encoding="utf-8")
        return racine

    def test_ce_qui_manque_est_dit(self):
        with tempfile.TemporaryDirectory() as dossier:
            constats = reglages_jeu.verifier(self.fichier(dossier, ShowAttackRadius="0"))
        self.assertEqual([c.bon for c in constats], [True, False, True, False])
        texte = reglages_jeu.rapport(constats)
        self.assertIn("À FAIRE  Afficher la portée d'attaque", texte)
        self.assertIn("À FAIRE  Touche « Cibler uniquement les champions »", texte)

    def test_tout_est_regle(self):
        with tempfile.TemporaryDirectory() as dossier:
            constats = reglages_jeu.verifier(self.fichier(dossier, evtChampionOnly="[Shift][c]"))
        self.assertTrue(all(c.bon for c in constats))

    def test_jeu_introuvable(self):
        with tempfile.TemporaryDirectory() as dossier:
            self.assertIsNone(reglages_jeu.verifier(Path(dossier)))
        self.assertIn("introuvables", reglages_jeu.rapport(None))


if __name__ == "__main__":
    unittest.main()
