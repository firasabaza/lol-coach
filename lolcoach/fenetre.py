"""Messagerie en jeu : des bulles qui apparaissent par-dessus la partie, puis s'effacent.

Rien ne reste à l'écran : une bulle disparaît quand son temps est écoulé ou dès que le conseil
est suivi. Seuls les minuteurs de sorts ennemis, que le joueur a lancés lui-même, restent visibles
tant qu'ils courent. La souris traverse tout : ni clic ni focus ne sont pris au jeu.

Ne s'affiche au-dessus de League of Legends qu'en mode fenêtré sans bordure.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEasingCurve, QObject, QPointF, QPropertyAnimation, QRectF, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QApplication, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)

LARGEUR = 400
MAX_BULLES = 3
RAYON = 12
GOUTTIERE = (12, 4, 12, 12)  # place laissée à l'ombre autour d'une carte : gauche, haut, droite, bas

FOND = QColor(15, 18, 24)
BORD = QColor(255, 255, 255, 22)
ENCRE = "#F4F5F7"
ENCRE_2 = "#C5CAD3"
POLICE = "Segoe UI"

# Une couleur par famille de conseil ; le rouge est réservé à l'urgence.
ACCENTS = {
    "danger": "#FF6B6B", "objectif": "#F2B84B", "or": "#4FD1C5", "build": "#4FD1C5",
    "vision": "#6FA8FF", "jungler": "#6FA8FF", "sort": "#B79CFF", "info": "#9AA4B2",
}
# Famille d'un conseil, d'après le début de sa clé.
GENRES = (
    (("drake", "baron", "grubs", "herald", "ame", "elder", "avantage", "sans-jungler", "etat", "plan-de-combat"), "objectif"),
    (("or-", "canon", "finir", "mort-or", "farm", "pv-"), "or"),
    (("build", "pic", "adc-pic", "items", "trinket", "pink"), "build"),
    (("vision",), "vision"),
    (("jungler", "gank", "crabes"), "jungler"),
    (("sort-",), "sort"),
    (("menace", "inferiorite", "niveau-eux", "support-mort", "morts", "ulti"), "danger"),
)


def genre(cle: str) -> str:
    return next((nom for prefixes, nom in GENRES if cle.startswith(prefixes)), "info")


class _Icone(QWidget):
    """Pastille carrée avec un pictogramme dessiné à la main, à la couleur de la famille."""

    def __init__(self, nom: str, couleur: QColor):
        super().__init__()
        self._nom, self._couleur = nom, couleur
        self.setFixedSize(30, 30)

    def paintEvent(self, _evenement) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pastille = QColor(self._couleur)
        pastille.setAlpha(40)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(pastille)
        p.drawRoundedRect(QRectF(0, 0, 30, 30), 8, 8)
        p.setPen(QPen(self._couleur, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        dessin = QPainterPath()
        if self._nom == "danger":  # triangle d'alerte
            dessin.moveTo(15, 7.5); dessin.lineTo(23.5, 22); dessin.lineTo(6.5, 22); dessin.closeSubpath()
            dessin.moveTo(15, 12.5); dessin.lineTo(15, 17)
            dessin.addEllipse(QPointF(15, 19.6), 0.3, 0.3)
        elif self._nom == "objectif":  # drapeau
            dessin.moveTo(10, 23); dessin.lineTo(10, 7.5)
            dessin.lineTo(21.5, 11.5); dessin.lineTo(10, 15.5)
        elif self._nom == "or":  # pièce
            dessin.addEllipse(QPointF(15, 15), 7.5, 7.5)
            dessin.addEllipse(QPointF(15, 15), 3, 3)
        elif self._nom == "build":  # losange d'objet
            dessin.moveTo(15, 7); dessin.lineTo(23, 15); dessin.lineTo(15, 23); dessin.lineTo(7, 15); dessin.closeSubpath()
            dessin.moveTo(11, 15); dessin.lineTo(19, 15)
        elif self._nom == "vision":  # œil
            dessin.moveTo(6.5, 15); dessin.quadTo(15, 6.5, 23.5, 15); dessin.quadTo(15, 23.5, 6.5, 15)
            dessin.addEllipse(QPointF(15, 15), 2.6, 2.6)
        elif self._nom == "jungler":  # radar
            dessin.addEllipse(QPointF(15, 15), 8, 8)
            dessin.moveTo(15, 15); dessin.lineTo(20.5, 9.5)
            dessin.addEllipse(QPointF(11.5, 17.5), 0.9, 0.9)
        elif self._nom == "sort":  # horloge
            dessin.addEllipse(QPointF(15, 15), 8, 8)
            dessin.moveTo(15, 10.5); dessin.lineTo(15, 15); dessin.lineTo(18.5, 17)
        else:  # bulle de dialogue
            dessin.addRoundedRect(QRectF(7, 8, 16, 11.5), 3.5, 3.5)
            dessin.moveTo(11.5, 19.5); dessin.lineTo(11.5, 23); dessin.lineTo(15.5, 19.5)
        p.drawPath(dessin)


class _Carte(QWidget):
    """Le corps d'une bulle : fond sombre arrondi, pictogramme, deux lignes de texte, jauge de temps."""

    def __init__(self, fait: str, action: str, famille: str, opacite: float):
        super().__init__()
        self._couleur = QColor(ACCENTS[famille])
        self._fond = QColor(FOND)
        self._fond.setAlphaF(opacite)
        self.reste = 1.0  # part du temps d'affichage encore à courir

        ligne = QHBoxLayout(self)
        g, h, d, b = GOUTTIERE
        ligne.setContentsMargins(g + 14, h + 12, d + 16, b + 15)
        ligne.setSpacing(12)
        ligne.addWidget(_Icone(famille, self._couleur), 0, Qt.AlignmentFlag.AlignTop)
        textes = QVBoxLayout()
        textes.setSpacing(3)
        ligne.addLayout(textes, 1)
        for texte, couleur, taille, graisse in (
            # Un conseil sans constat est une phrase entière : en gras, elle pèserait trop.
            (fait, ENCRE, 10.5, QFont.Weight.DemiBold if action or len(fait) < 60 else QFont.Weight.Normal),
            (action, ENCRE_2, 10, QFont.Weight.Normal),
        ):
            if not texte:
                continue
            etiquette = QLabel(texte)
            etiquette.setWordWrap(True)
            etiquette.setFont(QFont(POLICE, -1, graisse))
            etiquette.setStyleSheet(f"color: {couleur}; font-size: {taille}pt; background: transparent;")
            textes.addWidget(etiquette)

    def paintEvent(self, _evenement) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        g, h, d, b = GOUTTIERE
        cadre = QRectF(self.rect()).adjusted(g + 0.5, h + 0.5, -d - 0.5, -b - 0.5)
        # Ombre portée dessinée à la main : Qt ne sait pas emboîter une ombre dans un fondu.
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 11))
        for etalement in range(10, 0, -1):
            p.drawRoundedRect(cadre.adjusted(-etalement, 4 - etalement, etalement, 4 + etalement),
                              RAYON + etalement, RAYON + etalement)
        contour = QPainterPath()
        contour.addRoundedRect(cadre, RAYON, RAYON)
        p.fillPath(contour, self._fond)
        p.setPen(QPen(BORD, 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(contour)
        # Jauge : un trait à la couleur de la famille, qui se vide pendant que la bulle vit.
        p.setClipPath(contour)
        p.fillRect(QRectF(cadre.left(), cadre.bottom() - 2.5, cadre.width() * self.reste, 3), self._couleur)


class _Bulle(QWidget):
    """Une carte, son apparition, sa durée de vie et sa disparition."""

    def __init__(self, cle: str, fait: str, action: str, famille: str, duree: float, opacite: float,
                 a_la_fin: Callable[[_Bulle], None]):
        super().__init__()
        self.cle = cle
        self._a_la_fin = a_la_fin
        self._partie = False
        marge = QVBoxLayout(self)
        marge.setContentsMargins(0, 0, 0, 0)
        self._carte = _Carte(fait, action, famille, opacite)
        marge.addWidget(self._carte)

        self._voile = QGraphicsOpacityEffect(self)
        self._voile.setOpacity(0.0)
        self.setGraphicsEffect(self._voile)
        self._fondu = QPropertyAnimation(self._voile, b"opacity", self)
        self._fondu.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._vie = QVariantAnimation(self)
        self._vie.setStartValue(1.0)
        self._vie.setEndValue(0.0)
        self._vie.setDuration(int(duree * 1000))
        self._vie.valueChanged.connect(self._avancer)
        self._vie.finished.connect(self.partir)

    def entrer(self) -> None:
        self._fondu.setDuration(180)
        self._fondu.setStartValue(0.0)
        self._fondu.setEndValue(1.0)
        self._fondu.start()
        self._vie.start()

    def partir(self) -> None:
        if self._partie:
            return
        self._partie = True
        self._vie.stop()
        self._fondu.stop()
        self._fondu.setDuration(240)
        self._fondu.setStartValue(self._voile.opacity())
        self._fondu.setEndValue(0.0)
        self._fondu.finished.connect(lambda: self._a_la_fin(self))
        self._fondu.start()

    def _avancer(self, reste: float) -> None:
        self._carte.reste = reste
        self._carte.update()


class _Minuteurs(QWidget):
    """Pastilles des sorts ennemis notés par le joueur : « Flash Leona 4:20 »."""

    def __init__(self, opacite: float):
        super().__init__()
        self._lignes: list[tuple[str, float]] = []
        self._fond = QColor(FOND)
        self._fond.setAlphaF(opacite)
        self.setFixedHeight(34)
        self.hide()

    def montrer(self, lignes: list[tuple[str, float]]) -> None:
        self._lignes = lignes[:3]
        self.setVisible(bool(lignes))
        self.update()

    def paintEvent(self, _evenement) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        normal, gras = QFont(POLICE, 9), QFont(POLICE, 9, QFont.Weight.DemiBold)
        x = 12.0
        for libelle, secondes in self._lignes:
            temps = f"{int(max(secondes, 0)) // 60}:{int(max(secondes, 0)) % 60:02d}"
            p.setFont(normal)
            largeur_libelle = p.fontMetrics().horizontalAdvance(libelle)
            p.setFont(gras)
            largeur = 26 + largeur_libelle + 8 + p.fontMetrics().horizontalAdvance(temps) + 12
            pastille = QRectF(x, 3, largeur, 26)
            contour = QPainterPath()
            contour.addRoundedRect(pastille, 13, 13)
            p.fillPath(contour, self._fond)
            p.setPen(QPen(BORD, 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(contour)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(ACCENTS["sort"]))
            p.drawEllipse(QPointF(x + 14, 16), 3.5, 3.5)
            p.setFont(normal)
            p.setPen(QColor(ENCRE_2))
            p.drawText(QRectF(x + 26, 3, largeur_libelle, 26), Qt.AlignmentFlag.AlignVCenter, libelle)
            p.setFont(gras)
            p.setPen(QColor(ENCRE))
            p.drawText(QRectF(x + 26 + largeur_libelle + 8, 3, 60, 26), Qt.AlignmentFlag.AlignVCenter, temps)
            x += largeur + 8


class _Pont(QObject):
    """Fait exécuter une fonction dans le fil de l'interface, d'où qu'on l'appelle."""

    appel = Signal(object)


class Fenetre:
    def __init__(self, reglages: dict):
        self._app = QApplication.instance() or QApplication([])
        self._duree = float(reglages.get("duree", 9))
        self._opacite = float(reglages.get("opacite", 0.92))
        self._en_haut = "haut" in reglages.get("coin", "haut-gauche")
        self._bulles: list[_Bulle] = []

        self._racine = QWidget()
        self._racine.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self._racine.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._racine.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._pile = QVBoxLayout(self._racine)
        self._pile.setContentsMargins(0, 0, 0, 0)
        self._pile.setSpacing(0)
        self._minuteurs = _Minuteurs(self._opacite)
        self._pile.addWidget(self._minuteurs)
        self._pile.addStretch(1)
        if not self._en_haut:  # en bas de l'écran, la pile pousse vers le haut
            self._pile.insertStretch(0, 1)
            self._pile.takeAt(self._pile.count() - 1)

        ecran = QGuiApplication.primaryScreen().availableGeometry()
        marge = int(reglages.get("marge", 24))
        gauche = "gauche" in reglages.get("coin", "haut-gauche")
        x = ecran.left() + marge if gauche else ecran.right() - LARGEUR - marge
        self._racine.setGeometry(x, ecran.top() + marge, LARGEUR, ecran.height() - 2 * marge)

        self._pont = _Pont()
        self._pont.appel.connect(lambda fonction: fonction())

    # Les méthodes ci-dessous peuvent être appelées depuis n'importe quel fil.

    def conseil(self, cle: str, fait: str, action: str, urgent: bool = False) -> None:
        famille = "danger" if urgent else genre(cle)
        duree = self._duree * (1.3 if urgent else 1.0) + 0.04 * len(fait + action)
        self._pont.appel.emit(lambda: self._ajouter(cle, fait or action, action if fait else "", famille, duree))

    def retirer(self, cle: str) -> None:
        self._pont.appel.emit(lambda: [b.partir() for b in self._bulles if b.cle == cle])

    def minuteurs(self, lignes: list[tuple[str, float]]) -> None:
        self._pont.appel.emit(lambda: self._minuteurs.montrer(lignes))

    def message(self, titre: str, detail: str) -> None:
        self._pont.appel.emit(lambda: self._ajouter("message", titre, detail, "info", self._duree))

    def attente(self) -> None:
        self.message("Coach prêt", "En attente d'une partie.")

    def fermer(self) -> None:
        self._pont.appel.emit(self._app.quit)

    def lancer(self) -> None:
        """Bloque jusqu'à la fermeture. À appeler depuis le fil principal."""
        self._racine.show()
        self._app.exec()

    def _ajouter(self, cle: str, fait: str, action: str, famille: str, duree: float) -> None:
        for ancienne in [b for b in self._bulles if b.cle == cle]:
            ancienne.partir()
        while len([b for b in self._bulles if not b._partie]) >= MAX_BULLES:
            next(b for b in self._bulles if not b._partie).partir()
        bulle = _Bulle(cle, fait, action, famille, duree, self._opacite, self._oublier)
        self._bulles.append(bulle)
        # Sous les minuteurs quand la pile part du haut, au-dessus quand elle part du bas.
        position = self._pile.count() - 1 if self._en_haut else self._pile.indexOf(self._minuteurs)
        self._pile.insertWidget(position, bulle)
        bulle.entrer()

    def _oublier(self, bulle: _Bulle) -> None:
        if bulle in self._bulles:
            self._bulles.remove(bulle)
        self._pile.removeWidget(bulle)
        bulle.deleteLater()
