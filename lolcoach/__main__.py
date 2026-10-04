"""Le coach en direct.

    python -m lolcoach                  attend une partie et coache
    python -m lolcoach --simulation     joue la partie de démonstration, sans League of Legends
    python -m lolcoach --debrief FICHIER   refait le rapport d'une partie enregistrée
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
from pathlib import Path

from .client import Client
from .debrief import generer
from .enregistreur import Enregistreur
from .etat import Etat, depuis_json
from .moteur import Moteur
from .reglages import RACINE, Reglages, charger
from .suivi import Suivi

ABSENCES_AVANT_FIN = 5  # lectures vides d'affilée avant de considérer la partie finie
MODES = ("CLASSIC", "PRACTICETOOL")


def _temps(t: float) -> str:
    return f"{int(t) // 60}:{int(t) % 60:02d}"


def _hors_profil(e: Etat) -> str | None:
    """Pourquoi le coach ne sait pas coacher cette partie, ou None s'il sait."""
    if e.mode not in MODES:
        return f"le mode {e.mode} n'est pas pris en charge"
    if e.moi.role not in ("BOTTOM", ""):  # rôle vide en partie perso : on fait confiance au joueur
        return f"tu joues {e.moi.role} et le coach n'a que le profil ADC"
    return None


def _pied(e: Etat, s: Suivi) -> str:
    """La ligne du bas de la fenêtre : l'horloge et les deux prochains objectifs."""
    o = s.saison["objectifs"]
    drake = "Elder" if s.elder else "Drake"
    morceaux = [_temps(e.t), f"{drake} en vie" if s.drake_dispo(e.t) else f"{drake} {_temps(s.prochain_drake - e.t)}"]
    if e.t < o["grubs"]:
        morceaux.append(f"Grubs {_temps(o['grubs'] - e.t)}")
    elif e.t < o["herald"] and not s.herald_pris:
        morceaux.append(f"Herald {_temps(o['herald'] - e.t)}")
    else:
        morceaux.append("Baron en vie" if s.baron_dispo(e.t) else f"Baron {_temps(s.prochain_baron - e.t)}")
    return " · ".join(morceaux)


class Coach:
    def __init__(self, client: Client, reglages: Reglages, voix, fenetre, intervalle: float, une_partie: bool,
                 dossier: Path = RACINE):
        self.client = client
        self.reglages = reglages
        self.voix = voix
        self.fenetre = fenetre
        self.intervalle = intervalle
        self.une_partie = une_partie
        self.dossier = dossier
        self.rapport: Path | None = None
        self._stop = threading.Event()
        self._moteur: Moteur | None = None
        self._enregistreur: Enregistreur | None = None

    def arreter(self) -> None:
        self._stop.set()

    def tourner(self) -> None:
        absences = 0
        # Partie à ne plus lire : terminée (le jeu la sert encore quelques secondes) ou hors profil.
        ignoree = False
        print("En attente d'une partie...")
        try:
            while not self._stop.is_set():
                brut = self.client.lire()
                etat = depuis_json(brut) if brut else None
                if etat is None:
                    absences += 1
                    if absences >= ABSENCES_AVANT_FIN:
                        if self._moteur:
                            self._terminer()
                        elif ignoree and self.fenetre:
                            self.fenetre.attente()
                        ignoree = False
                    self._stop.wait(self.intervalle if self._moteur else min(2.0, self.intervalle * 2))
                    continue
                absences = 0
                if not ignoree and self._moteur is None and (raison := _hors_profil(etat)):
                    print(f"Partie ignorée : {raison}.")
                    if self.fenetre:
                        self.fenetre.message("Partie ignorée", raison[0].upper() + raison[1:] + ".")
                    ignoree = True
                if not ignoree:
                    self._lire(brut, etat)
                    if any(ev.nom == "GameEnd" for ev in etat.evenements):
                        self._terminer()
                        ignoree = True
                        if self.une_partie:
                            break
                self._stop.wait(self.intervalle)
        finally:
            if self._moteur:
                self._terminer()
            if self.voix:
                self.voix.fermer()
            if self.fenetre and (self.une_partie or self._stop.is_set()):
                self._stop.wait(3)  # le temps de lire « Partie terminée »
                self.fenetre.fermer()

    def _lire(self, brut: dict, etat: Etat) -> None:
        if self._moteur is None:
            self._moteur = Moteur(self.reglages)
            self._enregistreur = Enregistreur(self.dossier / "parties", etat.moi.champion)
            print(f"Partie détectée : {etat.moi.champion}, niveau « {self.reglages.niveau} ».")
        assert self._enregistreur is not None
        conseils = self._moteur.lire(etat)
        self._enregistreur.ecrire(brut)

        niveau = self.reglages.niveau
        dits = [c for c in conseils if c.texte(niveau)]
        for c in dits:
            print(f"[{_temps(etat.t)}] {c.texte(niveau)}")
        if self.voix:
            for c in dits[:2]:  # au plus deux phrases par lecture, les plus urgentes
                self.voix.dire(c.texte(niveau))
        if self.fenetre:
            if dits:
                c = dits[0]
                self.fenetre.conseil(c.fait, c.action if niveau == "coach" else "", c.priorite)
            self.fenetre.pied(_pied(etat, self._moteur.suivi))

    def _terminer(self) -> None:
        assert self._enregistreur is not None
        self._enregistreur.fermer()
        self.rapport = generer(self._enregistreur.chemin, self.reglages, self.dossier / "rapports")
        self._moteur = self._enregistreur = None
        print(f"Partie terminée. Débrief : {self.rapport}")
        if self.fenetre:
            self.fenetre.message("Partie terminée", "Le débrief est prêt.")
        if sys.stdout.isatty():
            os.startfile(self.rapport)


def main() -> None:
    arguments = argparse.ArgumentParser(prog="python -m lolcoach", description="Coach League of Legends en direct.")
    arguments.add_argument("--simulation", action="store_true", help="joue la partie de démonstration")
    arguments.add_argument("--vitesse", type=float, default=10.0, help="accélération de la simulation (défaut : 10)")
    arguments.add_argument("--muet", action="store_true", help="sans la voix")
    arguments.add_argument("--sans-fenetre", action="store_true", help="sans la mini fenêtre")
    arguments.add_argument("--debrief", metavar="FICHIER", help="refait le rapport d'une partie enregistrée")
    options = arguments.parse_args()

    for flux in (sys.stdout, sys.stderr):
        flux.reconfigure(encoding="utf-8", errors="replace")
    try:
        reglages = charger()
    except (ValueError, TypeError) as erreur:  # config.toml mal écrit : on le dit sans pile d'appels
        sys.exit(f"Réglages invalides : {erreur}")

    if options.debrief:
        rapport = generer(Path(options.debrief), reglages)
        print(f"Débrief : {rapport}")
        if sys.stdout.isatty():
            os.startfile(rapport)
        return

    serveur = None
    if options.simulation:
        from .simulateur import Serveur

        serveur = Serveur(options.vitesse, port=0)
        serveur.demarrer()
        client, intervalle = Client(serveur.url), 1.0 / options.vitesse
    else:
        client, intervalle = Client(), 1.0

    voix = fenetre = None
    if reglages.voix.get("active", True) and not options.muet and reglages.niveau != "silencieux":
        from .voix import Voix

        voix = Voix(reglages.voix)
    if reglages.fenetre.get("active", True) and not options.sans_fenetre:
        from .fenetre import Fenetre

        fenetre = Fenetre(reglages.fenetre)

    coach = Coach(client, reglages, voix, fenetre, intervalle, une_partie=options.simulation)
    fil = None
    try:
        if fenetre:
            # tkinter exige le fil principal : le coach tourne à côté.
            fil = threading.Thread(target=coach.tourner, daemon=True)
            fil.start()
            fenetre.lancer()
        else:
            coach.tourner()
    except KeyboardInterrupt:
        print("Coach arrêté.")
    finally:
        coach.arreter()
        if fil:
            fil.join(timeout=10)  # laisse le temps de fermer l'enregistrement et d'écrire le débrief
        if serveur:
            serveur.arreter()


if __name__ == "__main__":
    main()
