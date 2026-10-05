"""Raccourcis clavier globaux : signaler un sort d'invocateur ennemi, demander où aller, couper la voix.

Le coach ne voit ni les pings ni le chat : c'est le joueur qui lui dit ce qu'il a vu, et qui lui
parle. Les raccourcis ne sont pris à Windows que pendant une partie, pour ne pas gêner le reste.
"""

from __future__ import annotations

import ctypes
import queue
import threading
from ctypes import wintypes

WM_HOTKEY = 0x0312
ACTIVER, DESACTIVER = 0x8001, 0x8002  # messages privés (WM_APP + n) envoyés au fil des raccourcis
MODIFICATEURS = {"alt": 0x1, "ctrl": 0x2, "shift": 0x4, "win": 0x8}
SANS_REPETITION = 0x4000


def lire_raccourci(texte: str) -> tuple[int, int]:
    """« ctrl+f1 » -> (modificateurs, code de touche) au format de Windows."""
    *modificateurs, touche = texte.lower().replace(" ", "").split("+")
    try:
        masque = SANS_REPETITION
        for m in modificateurs:
            masque |= MODIFICATEURS[m]
        if touche.startswith("num") and touche[3:].isdigit():
            return masque, 0x60 + int(touche[3:])
        if touche.startswith("f") and touche[1:].isdigit() and 1 <= int(touche[1:]) <= 24:
            return masque, 0x70 + int(touche[1:]) - 1
        if len(touche) == 1 and touche.isalnum():
            return masque, ord(touche.upper())
    except KeyError:
        pass
    raise ValueError(f"raccourci incompris : {texte!r} (exemples : ctrl+f1, shift+f3, alt+num5)")


class Touches:
    def __init__(self, reglages: dict):
        # (modificateurs, touche, texte du réglage, (numéro de l'ennemi, "flash" | "autre")), puis les
        # commandes sans ennemi : (0, "direction"), (0, "voix").
        self._raccourcis = [
            (*lire_raccourci(texte), texte, (numero, quoi))
            for quoi in ("flash", "autre")
            for numero, texte in enumerate(reglages.get(quoi, []), start=1)
        ] + [(*lire_raccourci(texte), texte, (0, commande)) for commande, texte in reglages.get("commandes", {}).items()]
        self._file: queue.Queue[tuple[int, str]] = queue.Queue()
        self._refuses: list[str] = []
        self._fait = threading.Event()
        self._fil = 0
        threading.Thread(target=self._boucle, daemon=True).start()
        self._fait.wait()

    def activer(self) -> list[str]:
        """Prend les raccourcis. Rend ceux que Windows a refusés (déjà pris par un autre programme)."""
        self._envoyer(ACTIVER)
        return list(self._refuses)

    def desactiver(self) -> None:
        self._envoyer(DESACTIVER)

    def appuis(self) -> list[tuple[int, str]]:
        """Les appuis arrivés depuis le dernier appel : (numéro de l'ennemi, "flash" | "autre"), ou (0, commande)."""
        recus = []
        try:
            while True:
                recus.append(self._file.get_nowait())
        except queue.Empty:
            return recus

    def _envoyer(self, message: int) -> None:
        self._fait.clear()
        ctypes.windll.user32.PostThreadMessageW(self._fil, message, 0, 0)
        self._fait.wait(timeout=2)

    def _boucle(self) -> None:
        # Un raccourci appartient au fil qui l'a pris : tout se passe dans celui-ci.
        user32 = ctypes.windll.user32
        self._fil = ctypes.windll.kernel32.GetCurrentThreadId()
        message = wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(message), None, 0, 0, 0)  # crée la file de messages du fil
        self._fait.set()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            if message.message == WM_HOTKEY and 0 <= message.wParam < len(self._raccourcis):
                self._file.put(self._raccourcis[message.wParam][3])
            elif message.message == ACTIVER:
                self._refuses = [
                    texte for i, (masque, touche, texte, _) in enumerate(self._raccourcis)
                    if not user32.RegisterHotKey(None, i, masque, touche)
                ]
                self._fait.set()
            elif message.message == DESACTIVER:
                for i in range(len(self._raccourcis)):
                    user32.UnregisterHotKey(None, i)
                self._fait.set()
