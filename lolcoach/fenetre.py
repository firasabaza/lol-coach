"""Bandeau toujours au premier plan : le dernier conseil et les prochains timers.

Ne prend ni le clic ni le focus : la souris traverse la fenêtre et arrive au jeu.
Ne s'affiche au-dessus de League of Legends qu'en mode fenêtré sans bordure.
"""

from __future__ import annotations

import ctypes
import queue
import time
import tkinter as tk
from collections.abc import Callable

LARGEUR = 380
PEREMPTION = 12  # secondes après lesquelles un conseil passe en gris : il n'est plus d'actualité

FOND = "#14161A"
ENCRE = "#F2F3F5"
ENCRE_2 = "#C9CDD3"
DISCRET = "#8B93A1"
BARRE = {1: "#FF5C5C", 2: "#F2B84B", 3: "#6FA8FF", None: "#3A3F47"}
POLICE = "Segoe UI"


class Fenetre:
    def __init__(self, reglages: dict):
        self._coin = reglages.get("coin", "haut-gauche")
        self._marge = int(reglages.get("marge", 24))
        self._file: queue.Queue[Callable[[], None]] = queue.Queue()
        self._dit_a = 0.0

        self._tk = tk.Tk()
        self._tk.overrideredirect(True)
        self._tk.attributes("-topmost", True)
        self._tk.attributes("-alpha", float(reglages.get("opacite", 0.88)))
        self._tk.configure(bg=FOND)

        self._barre = tk.Frame(self._tk, bg=BARRE[None], width=4)
        self._barre.pack(side="left", fill="y")
        corps = tk.Frame(self._tk, bg=FOND, padx=12, pady=8)
        corps.pack(side="left", fill="both", expand=True)

        texte = {"bg": FOND, "anchor": "w", "justify": "left", "wraplength": LARGEUR - 4 - 24}
        self._fait = tk.Label(corps, fg=ENCRE, font=(POLICE, 13, "bold"), **texte)
        self._action = tk.Label(corps, fg=ENCRE_2, font=(POLICE, 12), **texte)
        self._pied = tk.Label(corps, fg=DISCRET, font=(POLICE, 10), **texte)
        self._fait.pack(fill="x")
        self._pied.pack(fill="x", pady=(4, 0))

        self._traverser()
        self.attente()

    # Les méthodes ci-dessous peuvent être appelées depuis n'importe quel fil.

    def attente(self) -> None:
        self._file.put(lambda: self._montrer("En attente d'une partie", "", None, "Lance League of Legends."))

    def message(self, titre: str, detail: str) -> None:
        self._file.put(lambda: self._montrer(titre, detail, None, ""))

    def conseil(self, fait: str, action: str, priorite: int) -> None:
        self._file.put(lambda: self._montrer(fait or action, action if fait else "", priorite, None))

    def pied(self, texte: str) -> None:
        self._file.put(lambda: self._pied.configure(text=texte))

    def fermer(self) -> None:
        self._file.put(self._tk.destroy)

    def lancer(self) -> None:
        """Bloque jusqu'à la fermeture. À appeler depuis le fil principal."""
        self._tk.after(100, self._battre)
        self._tk.mainloop()

    def _montrer(self, fait: str, action: str, priorite: int | None, pied: str | None) -> None:
        self._barre.configure(bg=BARRE[priorite])
        self._fait.configure(text=fait, fg=ENCRE)
        self._action.configure(text=action, fg=ENCRE_2)
        if action:
            self._action.pack(fill="x", after=self._fait)
        else:
            self._action.pack_forget()
        if pied is not None:
            self._pied.configure(text=pied)
        self._dit_a = time.monotonic() if priorite else 0.0
        self._placer()

    def _battre(self) -> None:
        try:
            while True:
                self._file.get_nowait()()
        except queue.Empty:
            pass
        except tk.TclError:
            return  # fenêtre détruite
        if self._dit_a and time.monotonic() - self._dit_a > PEREMPTION:
            self._barre.configure(bg=BARRE[None])
            self._fait.configure(fg=DISCRET)
            self._action.configure(fg=DISCRET)
            self._dit_a = 0.0
        self._tk.after(100, self._battre)

    def _placer(self) -> None:
        self._tk.update_idletasks()
        hauteur = self._tk.winfo_reqheight()
        x = self._marge if "gauche" in self._coin else self._tk.winfo_screenwidth() - LARGEUR - self._marge
        y = self._marge if "haut" in self._coin else self._tk.winfo_screenheight() - hauteur - self._marge
        self._tk.geometry(f"{LARGEUR}x{hauteur}+{x}+{y}")

    def _traverser(self) -> None:
        """Rend la fenêtre transparente aux clics et la sort de la barre des tâches."""
        self._tk.update_idletasks()
        user32 = ctypes.windll.user32
        user32.GetParent.restype = ctypes.c_void_p
        user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
        user32.GetWindowLongPtrW.argtypes = (ctypes.c_void_p, ctypes.c_int)
        user32.SetWindowLongPtrW.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t)
        fenetre = user32.GetParent(self._tk.winfo_id()) or self._tk.winfo_id()
        style_etendu = -20  # GWL_EXSTYLE
        couches, transparent, outil, sans_focus = 0x80000, 0x20, 0x80, 0x08000000
        style = user32.GetWindowLongPtrW(fenetre, style_etendu)
        user32.SetWindowLongPtrW(fenetre, style_etendu, style | couches | transparent | outil | sans_focus)
