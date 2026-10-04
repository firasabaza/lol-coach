"""Lecture de la Live Client Data API, servie par le jeu sur la boucle locale pendant une partie."""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from urllib.parse import urlsplit

URL_JEU = "https://127.0.0.1:2999"


class Client:
    def __init__(self, url: str = URL_JEU):
        if urlsplit(url).hostname not in ("127.0.0.1", "localhost"):
            raise ValueError(f"le coach ne lit que la boucle locale, pas {url}")
        self._url = url.rstrip("/") + "/liveclientdata/allgamedata"
        # Le jeu présente un certificat auto-signé ; sans risque puisqu'on ne sort pas de la machine.
        self._ssl = ssl.create_default_context()
        self._ssl.check_hostname = False
        self._ssl.verify_mode = ssl.CERT_NONE

    def lire(self) -> dict | None:
        """Le JSON complet de la partie, ou None s'il n'y a pas de partie en cours."""
        try:
            with urllib.request.urlopen(self._url, timeout=2, context=self._ssl) as reponse:
                return json.load(reponse)
        except (urllib.error.URLError, OSError, ValueError):
            return None
