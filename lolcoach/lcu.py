"""Lecture de l'API locale du client League of Legends : historique et chronologie des parties.

Le client écrit dans son dossier un fichier `lockfile` avec le port et le mot de passe de sa propre
API, valables tant qu'il est ouvert. On ne fait que lire, et seulement sur la boucle locale.
"""

from __future__ import annotations

import base64
import json
import ssl
import urllib.error
import urllib.request
from pathlib import Path

DOSSIER = Path(r"C:\Riot Games\League of Legends")


class ClientLol:
    def __init__(self, dossier: Path = DOSSIER):
        self._dossier = dossier
        # Certificat auto-signé du client ; sans risque puisqu'on ne sort pas de la machine.
        self._ssl = ssl.create_default_context()
        self._ssl.check_hostname = False
        self._ssl.verify_mode = ssl.CERT_NONE

    def lire(self, chemin: str):
        """Le JSON renvoyé par le client pour `chemin`, ou None s'il est fermé ou ne répond pas."""
        try:
            _, _, port, mot_de_passe, _ = (self._dossier / "lockfile").read_text(encoding="utf-8").split(":")
        except (OSError, ValueError):
            return None
        jeton = base64.b64encode(f"riot:{mot_de_passe}".encode()).decode()
        requete = urllib.request.Request(
            f"https://127.0.0.1:{port}{chemin}",
            headers={"Authorization": f"Basic {jeton}", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(requete, timeout=8, context=self._ssl) as reponse:
                return json.load(reponse)
        except (urllib.error.URLError, OSError, ValueError):
            return None
