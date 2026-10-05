"""Construit la version téléchargeable : un dossier avec lol-coach.exe, qui tourne sans Python.

    python -m pip install pyinstaller
    python construire.py

Le résultat est dist/lol-coach-<version>-windows.zip, à joindre à une release GitHub.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from lolcoach import __version__

RACINE = Path(__file__).resolve().parent
NOM = "lol-coach"
# Les données du patch et les repères tenus à la main. Les images se téléchargent à l'usage.
DONNEES = ("saison.toml", "objets.json", "champions.json", "champions_notes.toml")

ARRETER = "@echo off\r\nrem Arrete le coach.\r\ntaskkill /IM lol-coach.exe /F >nul 2>&1\r\n"

LISEZ_MOI = f"""lol-coach {__version__}
Coach League of Legends en direct pour ADC.

LANCER
  Double-clique sur lol-coach.exe, avant ou pendant la partie. Il n'ouvre pas de fenêtre : une
  pastille « Coach prêt » apparaît en haut à gauche de l'écran. Il détecte la partie, conseille
  par des bulles, ouvre l'après-match à la fin et attend la suivante.
  Le jeu doit être en « fenêtré sans bordure » pour que les bulles passent au-dessus.
  Pour l'arrêter : arreter.bat.

  Au premier lancement, Windows peut afficher « Windows a protégé votre ordinateur » : le
  programme n'est pas signé. « Informations complémentaires », puis « Exécuter quand même ».

EN PARTIE
  Ctrl+M            met et coupe la voix (coupée au lancement)
  Ctrl+F6           où aller maintenant ; un deuxième appui donne la solution suivante
  Ctrl+F1 à F5      note le Flash de l'ennemi 1 à 5 (ordre du tableau des scores)
  Shift+F1 à F5     note son autre sort d'invocateur
  Ces touches ne sont prises à Windows que pendant une partie.

  Le coach ne suit que les parties jouées en ADC (Faille de l'invocateur et outil d'entraînement).
  Dans un autre rôle, il ignore la partie.

RÉGLER
  config.toml, à côté de l'exécutable : niveau de conseil, voix, coin de l'écran, touches, seuils.
  Après un patch : lol-coach.exe --maj-donnees met à jour les objets et les champions.
  Pour voir une partie de démonstration sans lancer le jeu : lol-coach.exe --simulation

FICHIERS CRÉÉS
  journal.log   ce que le coach a dit pendant la dernière session
  parties/      l'enregistrement de chaque partie
  rapports/     les pages d'après-match

CE QU'IL LIT
  Uniquement l'API locale officielle du jeu (127.0.0.1:2999) et, pour l'après-match, celle du
  client League. Il ne lit ni la mémoire du jeu ni l'écran, et n'envoie aucune touche au jeu.
  Rien ne sort de ta machine, sauf le téléchargement des données et images publiques du patch.

À SAVOIR
  Outil personnel, sans lien avec Riot Games et non approuvé par Riot. Les règles de Riot sur les
  outils tiers n'approuvent pas les consignes données en direct pendant une partie : le niveau
  « coach » est un choix que tu fais pour ton compte. Dans config.toml, niveau = "faits" ne garde
  que les constats, et niveau = "silencieux" ne garde que l'après-match.

Code source et détails : https://github.com/firasabaza/lol-coach
"""


def construire() -> Path:
    with tempfile.TemporaryDirectory() as temporaire:
        travail = Path(temporaire)
        lanceur = travail / "lanceur.py"
        lanceur.write_text("from lolcoach.__main__ import main\n\nmain()\n", encoding="utf-8")
        subprocess.run(
            [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--name", NOM,
             "--paths", str(RACINE), "--distpath", str(travail / "dist"), "--workpath", str(travail / "build"),
             "--specpath", str(travail), "--exclude-module", "tkinter", str(lanceur)],
            check=True, cwd=RACINE,
        )
        dossier = travail / "dist" / NOM
        # Réglages et données à côté de l'exécutable : le joueur les modifie, le coach les met à jour.
        shutil.copy(RACINE / "config.toml", dossier)
        (dossier / "donnees").mkdir()
        for nom in DONNEES:
            shutil.copy(RACINE / "donnees" / nom, dossier / "donnees")
        (dossier / "arreter.bat").write_bytes(ARRETER.encode("ascii"))
        (dossier / "LISEZ-MOI.txt").write_text(LISEZ_MOI, encoding="utf-8-sig", newline="\r\n")

        archive = RACINE / "dist" / f"{NOM}-{__version__}-windows.zip"
        archive.parent.mkdir(exist_ok=True)
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for fichier in sorted(dossier.rglob("*")):
                if fichier.is_file():
                    z.write(fichier, Path(NOM) / fichier.relative_to(dossier))
    return archive


if __name__ == "__main__":
    print(f"Archive prête : {construire()}")
