"""Règles de coaching de l'ADC. Chaque règle lit la partie et propose des conseils.

Les principes et leurs sources sont dans docs/CONNAISSANCES.md.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass

from .etat import PINK, ROLES_BOT, Etat
from .reglages import Reglages
from .suivi import Suivi, tour_bot

URGENT, TEMPO, INFO = 1, 2, 3


@dataclass(frozen=True)
class Conseil:
    cle: str  # une même clé n'est dite qu'une fois, sauf repeter_apres
    priorite: int
    fait: str  # ce qu'on constate
    action: str  # ce que le coach en conclut
    repeter_apres: float | None = None

    def texte(self, niveau: str) -> str:
        if niveau == "coach":
            return f"{self.fait} {self.action}".strip()
        if niveau == "faits":
            return self.fait
        return ""


Regle = Callable[[Etat, Suivi, Reglages], Iterator[Conseil]]


def duree(secondes: float) -> str:
    s = max(0, round(secondes))
    if s < 60:
        return f"{s} secondes"
    minutes, reste = divmod(s, 60)
    base = "une minute" if minutes == 1 else f"{minutes} minutes"
    return base if reste == 0 else f"{base} {reste}"


def heure(t: float) -> str:
    """Une heure de jeu telle qu'on la dit : « 12 minutes 40 »."""
    minutes, secondes = divmod(max(0, round(t)), 60)
    return f"{minutes} minutes {secondes}" if secondes else f"{minutes} minutes"


def _or(x: float) -> int:
    return int(x // 50 * 50)


def _annonce(reste: float, seuils: tuple[int, ...]) -> int | None:
    """Le palier d'annonce dans lequel on se trouve : 60 entre 60 s et 30 s, 30 en dessous."""
    paliers = sorted(seuils, reverse=True)
    for i, palier in enumerate(paliers):
        plancher = paliers[i + 1] if i + 1 < len(paliers) else 0
        if plancher < reste <= palier:
            return palier
    return None


def debut(e: Etat, s: Suivi, c: Reglages) -> Iterator[Conseil]:
    if not s.premiere:
        return
    if e.t > 90:
        yield Conseil("debut", INFO, "Coach connecté.", "")
        return
    adc, sup, jungler = e.ennemi("BOTTOM"), e.ennemi("UTILITY"), e.jungler_ennemi
    fait = "Coach prêt."
    if adc and sup:
        fait += f" {e.moi.champion} contre {adc.champion} et {sup.champion}."
    if jungler:
        fait += f" Leur jungler : {jungler.champion}."
    yield Conseil("debut", INFO, fait, "")


def niveaux(e: Etat, s: Suivi, c: Reglages) -> Iterator[Conseil]:
    if 75 <= e.t < 100:
        melees = c.saison["niveaux"]["sbires_niveau_2_duo"] - 6
        yield Conseil(
            "niveau-2-rappel", INFO, "",
            f"Niveau 2 à la première vague plus {melees} mêlées. Pousse pour l'avoir avant eux.",
        )

    duo = [j for j in e.ennemis if j.role in ROLES_BOT]
    if not duo:
        return
    eux = max(j.niveau for j in duo)
    for n in (2, 3, 6):
        if eux >= n > e.moi.niveau:
            yield Conseil(
                f"niveau-eux-{n}", URGENT, f"Ils passent niveau {n} avant toi.",
                "Recule, pas de trade tant que tu n'y es pas.",
            )
        elif e.moi.niveau >= n > eux:
            action = (
                "Tu as ton ulti avant eux : cherche l'all-in si ton support suit."
                if n == 6
                else "Avance et trade maintenant."
            )
            yield Conseil(f"niveau-moi-{n}", TEMPO, f"Niveau {n} avant eux.", action)


def drake(e: Etat, s: Suivi, c: Reglages) -> Iterator[Conseil]:
    reste = s.prochain_drake - e.t
    cle = f"drake-{int(s.prochain_drake)}"
    point_ame = c.saison["objectifs"]["drakes_pour_ame"] - 1
    ame_nous = s.drakes[e.moi.equipe] == point_ame
    ame_eux = any(n == point_ame for equipe, n in s.drakes.items() if equipe != e.moi.equipe)
    nom = "Elder" if s.elder else "Drake d'âme" if ame_nous or ame_eux else "Drake"

    if 60 < reste <= 90 and not e.moi.mort and e.or_ >= c.seuils.or_reset_objectif:
        yield Conseil(
            f"{cle}-reset", TEMPO, f"{nom} dans {duree(round(reste / 10) * 10)} et {_or(e.or_)} gold.",
            "Reset maintenant pour arriver avec tes items.",
        )

    palier = _annonce(reste, c.seuils.annonces_objectif)
    if palier is None:
        return
    dernier = palier == min(c.seuils.annonces_objectif)
    if s.elder:
        action = "Reste derrière ta frontline." if dernier else "Groupe et pose la vision. Personne ne meurt avant."
    elif ame_eux:
        action = "C'est leur point d'âme : tout le monde descend."
    elif ame_nous:
        action = "C'est ton point d'âme : vague poussée, vision, et on le prend."
    elif not s.en_lane(e):
        action = "Pousse mid, puis décale côté bot avec l'équipe."
    elif dernier:
        action = "Décale avec ton support, vague poussée d'abord."
    else:
        action = "Pousse ta vague maintenant, puis ward la rivière."
    yield Conseil(f"{cle}-{palier}", TEMPO, f"{nom} dans {duree(round(reste / 5) * 5)}.", action)


def objectifs_haut(e: Etat, s: Suivi, c: Reglages) -> Iterator[Conseil]:
    o = c.saison["objectifs"]
    premier = (max(c.seuils.annonces_objectif),)

    reste = o["grubs"] - e.t
    if _annonce(reste, premier):
        yield Conseil(
            "grubs", INFO, f"Grubs dans {duree(round(reste / 5) * 5)}.",
            "Ton jungler part en haut : joue safe en bot, pas de trade sans vision.",
        )

    reste = o["herald"] - e.t
    if _annonce(reste, premier) and not s.herald_pris:
        yield Conseil(
            "herald", INFO, f"Herald dans {duree(round(reste / 5) * 5)}.",
            "C'est en haut : pousse ta vague et reste prêt à décaler.",
        )

    reste = s.prochain_baron - e.t
    palier = _annonce(reste, c.seuils.annonces_objectif)
    if palier:
        yield Conseil(
            f"baron-{int(s.prochain_baron)}-{palier}", TEMPO, f"Baron dans {duree(round(reste / 5) * 5)}.",
            "Groupe mid, vision côté Baron, ne reste pas seul en side.",
        )


def recall(e: Etat, s: Suivi, c: Reglages) -> Iterator[Conseil]:
    if s.mort_ce_tour and e.or_ >= 0.8 * c.seuils.or_recall:
        yield Conseil(
            f"mort-or-{e.moi.morts}", INFO, f"Mort avec {_or(e.or_)} gold en poche.",
            "Ce back, il fallait le prendre avant.",
        )
    # Juste après une réapparition ou un achat on est à la fontaine : lui dire de back n'a pas de sens.
    if e.moi.mort or e.t - s.reapparu_a < 20 or (s.nb_achats and e.t - s.dernier_achat < 20):
        return

    lane = s.en_lane(e)
    canon = s.prochain_canon(e.t) - e.t
    if e.or_ >= c.seuils.or_dormant:
        yield Conseil(
            f"or-dormant-{s.nb_achats}", TEMPO, f"{_or(e.or_)} gold non dépensés.",
            "Tu joues avec un item de moins. Reset maintenant.", repeter_apres=90,
        )
    elif e.or_ >= c.seuils.or_recall:
        if lane and canon <= 25:
            action = "Crash la vague canon qui arrive, puis back."
        elif lane:
            action = "Crash ta vague et back pour ton composant."
        else:
            action = "Reset dès que ta vague est poussée."
        yield Conseil(f"or-{s.nb_achats}", TEMPO, f"{_or(e.or_)} gold.", action)
        attend = s.or_seuil_depuis is not None and e.t - s.or_seuil_depuis > 20
        if lane and canon <= 20 and attend:
            yield Conseil(
                f"canon-{s.nb_achats}", TEMPO, f"Vague canon dans {duree(canon)}.",
                "C'est celle-là qu'on crash avant de back.",
            )

    if len(s.pv) < (s.pv.maxlen or 0):
        return
    stable = max(s.pv)  # bas depuis plusieurs lectures, pas juste pendant un trade
    if stable <= c.seuils.pv_critique:
        yield Conseil(
            "pv-critique", URGENT, "PV critiques.", "Back tout de suite, n'attends pas la vague.",
            repeter_apres=60,
        )
    elif stable <= c.seuils.pv_bas:
        action = (
            f"Avec {_or(e.or_)} gold, pousse si tu peux et back."
            if e.or_ >= 500
            else "Joue derrière ta vague, pas de trade."
        )
        yield Conseil("pv-bas", TEMPO, "PV bas.", action, repeter_apres=90)


def vision(e: Etat, s: Suivi, c: Reglages) -> Iterator[Conseil]:
    if e.moi.mort:
        return
    silence = e.t - s.derniere_vision
    if silence >= c.seuils.vision_silence:
        action = "Pose ton trinket : rivière ou tribush." if s.en_lane(e) else "Pose ta ward avant d'avancer."
        yield Conseil(
            "vision", INFO, f"Pas de vision posée depuis {duree(round(silence / 30) * 30)}.", action,
            repeter_apres=180,
        )
    # Quelques secondes après le dernier achat : encore à la boutique, le panier est fini.
    if e.t >= 360 and 6 <= e.t - s.dernier_achat <= 12 and not e.moi.possede(PINK):
        yield Conseil(
            f"pink-{s.nb_achats}", INFO, "Pas de pink dans ton inventaire.",
            "75 gold : prends-en une à chaque back.",
        )


def jungler(e: Etat, s: Suivi, c: Reglages) -> Iterator[Conseil]:
    jg = e.jungler_ennemi
    if jg is None:
        return
    j = c.saison["jungle"]

    if j["gank_niveau_3"] - 10 <= e.t < j["gank_niveau_3"] + 15:
        yield Conseil(
            "gank-niveau-3", TEMPO, "",
            "Premier gank possible. Ward la rivière et garde la vague au milieu.",
        )
    if j["crabe"] - 5 <= e.t < j["crabe"] + 10:
        yield Conseil(
            "crabes", INFO, "Crabes dans quelques secondes.",
            "Leur jungler sort de son clear par la rivière : pas de push sans vision.",
        )
    if jg.niveau >= 6:
        yield Conseil(
            "jungler-6", TEMPO, "Leur jungler est niveau 6.",
            "Gank avec ulti possible : reste du côté de ta vision.",
        )

    if jg.mort and jg.reapparition >= 10 and not e.moi.mort:
        if sum(j.mort for j in e.ennemis) >= 3:
            return  # la règle d'avantage numérique le dit déjà, en mieux
        action = (
            "Drake gratuit : ping ton jungler et pousse."
            if s.drake_dispo(e.t)
            else "Tu peux pousser et warder sans risque."
        )
        yield Conseil(
            f"jungler-mort-{jg.morts}", TEMPO, f"Leur jungler est mort, {duree(jg.reapparition)}.", action
        )
        return

    lane = s.en_lane(e)
    if s.jungler_vu:
        t_vu, cote, indice = s.jungler_vu
        cle = f"jungler-vu-{int(t_vu)}"
        traversee = j["traversee_carte"]
        if not s.jungler_vu_ce_tour:
            # Il s'était montré en haut : une fois le temps de traverser écoulé, la fenêtre se referme.
            if lane and cote == "top" and traversee <= e.t - t_vu < traversee + 20:
                yield Conseil(
                    f"jungler-fenetre-{int(t_vu)}", TEMPO, f"Leur jungler était top il y a {duree(traversee)}.",
                    "Ta fenêtre est finie, il a eu le temps de descendre. "
                    "Avancé : recule. Sous tour : c'est le moment de back.",
                )
        elif cote == "top" and s.drake_dispo(e.t):
            yield Conseil(
                cle, TEMPO, "Leur jungler vient d'apparaître en top.",
                "Il est loin : drake possible, ping ton jungler.",
            )
        elif cote == "top" and lane:
            yield Conseil(
                cle, TEMPO, "Leur jungler vient d'apparaître en top.",
                f"Tu es safe {traversee} secondes : joue agressif ou prends la vision rivière.",
            )
        elif cote == "mid" and lane:
            yield Conseil(
                cle, TEMPO, "Leur jungler vient d'apparaître mid.", "Il peut descendre vite. Avancé : recule."
            )
        elif cote == "bot" and indice == "objectif" and lane:
            yield Conseil(
                cle, URGENT, "Leur jungler vient de prendre le drake, il est côté bot.",
                "Avancé : recule, gank probable. Sous tour : c'est le moment de back.",
            )
        elif cote == "base" and lane:
            yield Conseil(
                cle, INFO, "Leur jungler est de retour en jeu.",
                f"Compte {j['base_vers_bot']} secondes avant qu'il puisse être bot.",
            )

    sans_nouvelle = e.t - s.jungler_nouvelle
    if lane and sans_nouvelle >= c.seuils.jungler_inconnu and e.t - s.derniere_vision >= 60:
        depuis = "plus de 3 minutes" if sans_nouvelle > 180 else duree(round(sans_nouvelle / 15) * 15)
        yield Conseil(
            "jungler-inconnu", INFO, f"Leur jungler n'a pas été vu depuis {depuis}.",
            "Sans vision, ne dépasse pas le milieu de la lane.", repeter_apres=150,
        )


def avantage(e: Etat, s: Suivi, c: Reglages) -> Iterator[Conseil]:
    morts = [j for j in e.ennemis if j.mort]

    if len(morts) >= 3 and not e.moi.mort:
        if s.baron_dispo(e.t):
            action = "Baron, maintenant."
        elif s.drake_dispo(e.t):
            action = "Drake, maintenant."
        else:
            action = "Prends une tour, pas de back."
        yield Conseil("avantage", URGENT, f"{len(morts)} ennemis morts.", action, repeter_apres=45)
        return

    if not s.en_lane(e):
        return
    support = e.allie("UTILITY")
    if support and support.mort and not e.moi.mort:
        yield Conseil(
            f"support-mort-{support.morts}", URGENT, "Ton support est mort.",
            "Tu es seul : recule sous ta tour et farm ce qui vient.",
        )
    if e.moi.mort:
        return
    duo_mort = [j for j in morts if j.role in ROLES_BOT and j.reapparition >= 12]
    if len(duo_mort) == 2:
        yield Conseil(
            f"duo-mort-{sum(j.morts for j in duo_mort)}", TEMPO, "Leur botlane est morte.",
            "Crash la vague, prends les plaques, puis back.",
        )
    elif len(duo_mort) == 1:
        j = duo_mort[0]
        role = "ADC" if j.role == "BOTTOM" else "support"
        yield Conseil(
            f"duo-mort-{j.nom}-{j.morts}", TEMPO, f"Leur {role} est mort, {duree(j.reapparition)}.",
            "Deux contre un : pousse et mets la pression, sans dive.",
        )


def farm(e: Etat, s: Suivi, c: Reglages) -> Iterator[Conseil]:
    for minute in (6, 10, 15, 20, 25):
        if minute * 60 <= e.t < minute * 60 + 30:
            rythme = e.moi.cs / minute
            action = (
                "Bon rythme, continue."
                if rythme >= c.seuils.cs_par_minute
                else f"Sous l'objectif de {c.seuils.cs_par_minute:g}. Priorité au farm."
            )
            lu = f"{rythme:.1f}".replace(".", ",")
            yield Conseil(f"farm-{minute}", INFO, f"{minute} minutes : {e.moi.cs} sbires, {lu} par minute.", action)


def items(e: Etat, s: Suivi, c: Reglages) -> Iterator[Conseil]:
    adc = e.ennemi("BOTTOM")
    if adc is None:
        return
    ecart = adc.valeur_objets - e.moi.valeur_objets
    palier = abs(ecart) // c.seuils.ecart_items
    if palier == 0:
        return
    montant = round(abs(ecart) / 100) * 100
    if ecart > 0:
        yield Conseil(
            f"items-retard-{palier}", INFO, f"Leur ADC a {montant} gold d'items de plus que toi.",
            "Pas de trade long. Farm et attends ton prochain back.",
        )
    else:
        yield Conseil(
            f"items-avance-{palier}", TEMPO, f"Tu as {montant} gold d'items d'avance sur leur ADC.",
            "C'est ta fenêtre : force les trades.",
        )


def tours(e: Etat, s: Suivi, c: Reglages) -> Iterator[Conseil]:
    for ev in s.nouveaux:
        if ev.nom != "TurretKilled":
            continue
        if ev.cible == tour_bot(e.moi.equipe):
            yield Conseil(
                "tour-bot-perdue", TEMPO, "Ta tour bot est tombée.",
                "La lane est trop longue : va farm mid, ne reste pas seul en bot.",
            )
        elif ev.cible in (tour_bot("ORDER"), tour_bot("CHAOS")):
            yield Conseil(
                "tour-bot-prise", TEMPO, "Tour bot ennemie détruite.",
                "Va mid avec ton support. La side, c'est pour ton toplaner.",
            )

    fin = c.saison["sbires"]["fin_de_lane"]
    if fin <= e.t < fin + 30:
        yield Conseil(
            "fin-de-lane", INFO, f"{duree(fin)}, fin de la phase de lane.",
            "Les vagues accélèrent : farm mid et groupe aux objectifs.",
        )


def sorts(e: Etat, s: Suivi, c: Reglages) -> Iterator[Conseil]:
    """Minuteurs des sorts d'invocateur ennemis que le joueur a signalés lui-même."""
    for genre, objet in s.notes:
        if isinstance(objet, str):
            yield Conseil(f"sort-refus-{int(e.t)}-{objet}", INFO, objet, "")
        elif genre == "annule":
            yield Conseil(
                f"sort-annule-{objet.champion}-{objet.sort}-{int(e.t)}", INFO,
                f"{objet.sort} de {objet.champion} : minuteur annulé.", "",
            )
        else:
            action = (
                f"Pas de Flash pendant {duree(objet.retour - objet.note_a)} : c'est la fenêtre pour l'attraper."
                if objet.sort == "Flash"
                else ""
            )
            yield Conseil(
                f"sort-note-{objet.champion}-{objet.sort}-{int(objet.note_a)}", INFO,
                f"{objet.sort} de {objet.champion} noté, retour à {heure(objet.retour)}.", action,
            )

    for m in s.sorts.values():
        reste = m.retour - e.t
        cle = f"{m.champion}-{m.sort}-{int(m.note_a)}"
        if 5 < reste <= 30:
            action = "Dernière fenêtre pour l'attraper." if m.sort == "Flash" else ""
            yield Conseil(f"sort-bientot-{cle}", TEMPO, f"{m.sort} de {m.champion} dans {duree(round(reste / 5) * 5)}.", action)
        elif reste <= 0:
            yield Conseil(f"sort-retour-{cle}", INFO, f"{m.sort} de {m.champion} de nouveau disponible.", "")


REGLES: tuple[Regle, ...] = (
    debut, niveaux, drake, objectifs_haut, recall, vision, jungler, avantage, farm, items, tours, sorts,
)
