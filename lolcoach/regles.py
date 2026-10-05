"""Règles de coaching de l'ADC. Chaque règle lit la partie et propose des conseils.

Les principes et leurs sources sont dans docs/CONNAISSANCES.md.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass

from .achats import a_la_boutique, finissable
from .compo import est
from .etat import PINK, ROLES_BOT, Etat
from .rapport import ECRASANT, NET, avance, avance_lane, ennemis_morts, forme, score
from .reglages import Reglages
from .suivi import Suivi, lire_structure

URGENT, TEMPO, INFO = 1, 2, 3


@dataclass(frozen=True)
class Conseil:
    cle: str  # une même clé n'est dite qu'une fois, sauf repeter_apres
    priorite: int
    fait: str  # ce qu'on constate
    action: str  # ce que le coach en conclut
    repeter_apres: float | None = None
    # Ce que le conseil demande au joueur : « danger », « objectif », « agressif », « back » ou
    # « prudent ». Le moteur s'en sert pour ne jamais dire deux choses contraires (moteur.py).
    intention: str = ""

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


def or_en_poche(e: Etat) -> float:
    """L'or que le joueur peut encore transformer en puissance.

    Zéro quand le build est fini (il n'y a plus rien à acheter), et quand l'outil d'entraînement
    en a donné des dizaines de milliers.
    """
    if e.moi.build_complet or (e.mode == "PRACTICETOOL" and e.or_ > 10000):
        return 0.0
    return e.or_


def accompli(conseil: Conseil, dit_a: float, e: Etat, s: Suivi) -> bool:
    """Le joueur a-t-il fait ce que le conseil demandait ? Sert à retirer le message de l'écran."""
    cle = conseil.cle
    if cle.startswith("pv-"):
        return e.pv > 0.6 or s.dernier_achat > dit_a
    if cle.startswith(("or-", "canon-", "finir-", "boutique-")) or cle.endswith("-reset"):
        return s.dernier_achat > dit_a
    if cle.startswith("viser-"):
        return e.moi.possede(int(cle.removeprefix("viser-")))
    if cle == "vision":
        return s.derniere_vision > dit_a
    if cle == "pink":
        return e.moi.possede(PINK)
    return False


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
            if avance_lane(e) >= NET:
                continue  # un niveau de retard ne pèse pas contre une vraie avance en objets
            yield Conseil(
                f"niveau-eux-{n}", URGENT, f"Ils passent niveau {n} avant toi.",
                "Recule, pas de trade tant que tu n'y es pas.", intention="prudent",
            )
        elif e.moi.niveau >= n > eux:
            action = (
                "Tu as ton ulti avant eux : cherche l'all-in si ton support suit."
                if n == 6
                else "Avance et trade maintenant."
            )
            yield Conseil(f"niveau-moi-{n}", TEMPO, f"Niveau {n} avant eux.", action, intention="agressif")


def drake(e: Etat, s: Suivi, c: Reglages) -> Iterator[Conseil]:
    reste = s.prochain_drake - e.t
    cle = f"drake-{int(s.prochain_drake)}"
    point_ame = c.saison["objectifs"]["drakes_pour_ame"] - 1
    ame_nous = s.drakes[e.moi.equipe] == point_ame
    ame_eux = any(n == point_ame for equipe, n in s.drakes.items() if equipe != e.moi.equipe)
    nom = "Elder" if s.elder else "Drake d'âme" if ame_nous or ame_eux else "Drake"

    if 60 < reste <= 90 and not e.moi.mort and or_en_poche(e) >= c.seuils.or_reset_objectif:
        yield Conseil(
            f"{cle}-reset", TEMPO, f"{nom} dans {duree(round(reste / 10) * 10)} et {_or(or_en_poche(e))} gold.",
            "Reset maintenant pour arriver avec tes items.", intention="back",
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
    yield Conseil(f"{cle}-{palier}", TEMPO, f"{nom} dans {duree(round(reste / 5) * 5)}.", action, intention="tempo")


def objectifs_haut(e: Etat, s: Suivi, c: Reglages) -> Iterator[Conseil]:
    o = c.saison["objectifs"]
    premier = (max(c.seuils.annonces_objectif),)

    reste = o["grubs"] - e.t
    if _annonce(reste, premier):
        if avance_lane(e) >= NET:
            # Les deux junglers montent : en bas c'est du deux contre deux, et tu es devant.
            yield Conseil(
                "grubs", INFO, f"Grubs dans {duree(round(reste / 5) * 5)}.",
                "Les junglers montent : en bot c'est du deux contre deux et tu es devant. Force le trade ou les plaques.",
                intention="agressif",
            )
        else:
            yield Conseil(
                "grubs", INFO, f"Grubs dans {duree(round(reste / 5) * 5)}.",
                "Ton jungler part en haut : pas de trade sans vision de la rivière.", intention="prudent",
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
            "Groupe mid, vision côté Baron, ne reste pas seul en side.", intention="tempo",
        )


def recall(e: Etat, s: Suivi, c: Reglages) -> Iterator[Conseil]:
    if s.mort_ce_tour and or_en_poche(e) >= 0.8 * c.seuils.or_recall:
        yield Conseil(
            f"mort-or-{e.moi.morts}", INFO, f"Mort avec {_or(or_en_poche(e))} gold en poche.",
            "Ce back, il fallait le prendre avant.",
        )
    if e.moi.build_complet:
        yield Conseil(
            "build-complet", INFO, "Build terminé.",
            "Ton or ne sert plus qu'aux élixirs : prends-en un avant chaque gros objectif.",
        )
    # Juste après une réapparition ou un achat on est à la fontaine : lui dire de back n'a pas de sens.
    if e.moi.mort or e.t - s.reapparu_a < 20 or (s.nb_achats and e.t - s.dernier_achat < 20):
        return
    # Trois ennemis morts : la carte est libre, on prend quelque chose. Le back et les PV attendront.
    if ennemis_morts(e) >= 3:
        return

    lane = s.en_lane(e)
    canon = s.prochain_canon(e.t) - e.t
    if or_en_poche(e) >= c.seuils.or_dormant:
        yield Conseil(
            f"or-dormant-{s.nb_achats}", TEMPO, f"{_or(or_en_poche(e))} gold non dépensés.",
            "Tu joues avec un item de moins. Reset maintenant.", repeter_apres=90, intention="back",
        )
    elif or_en_poche(e) >= c.seuils.or_recall and finissable(e, or_en_poche(e)) is None:
        achat = a_la_boutique(e, or_en_poche(e))
        boutique = f" À la boutique : {achat}." if achat else ""
        if lane and canon <= 25:
            action = f"Crash la vague canon qui arrive, puis back.{boutique}"
        elif lane:
            action = f"Crash ta vague et back.{boutique}"
        else:
            action = f"Reset dès que ta vague est poussée.{boutique}"
        yield Conseil(f"or-{s.nb_achats}", TEMPO, f"{_or(or_en_poche(e))} gold.", action, intention="back")
        attend = s.or_seuil_depuis is not None and e.t - s.or_seuil_depuis > 20
        if lane and canon <= 20 and attend:
            yield Conseil(
                f"canon-{s.nb_achats}", TEMPO, f"Vague canon dans {duree(canon)}.",
                "C'est celle-là qu'on crash avant de back.", intention="back",
            )

    if len(s.pv) < (s.pv.maxlen or 0):
        return
    stable = max(s.pv)  # bas depuis plusieurs lectures, pas juste pendant un trade
    if stable <= c.seuils.pv_critique:
        yield Conseil(
            "pv-critique", URGENT, "PV critiques.", "Back tout de suite, n'attends pas la vague.",
            repeter_apres=60, intention="danger",
        )
    elif stable <= c.seuils.pv_bas:
        action = (
            f"Avec {_or(or_en_poche(e))} gold, pousse si tu peux et back."
            if or_en_poche(e) >= 500
            else "Joue derrière ta vague, pas de trade."
        )
        yield Conseil("pv-bas", TEMPO, "PV bas.", action, repeter_apres=90, intention="back")


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
    if e.t >= 360 and 6 <= e.t - s.dernier_achat <= 12 and not e.moi.possede(PINK) and e.moi.place_libre:
        yield Conseil(
            "pink", INFO, "Pas de pink dans ton inventaire.", "75 gold : prends-en une avant de repartir.",
            repeter_apres=300,
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
    if jg.niveau >= 6 and not est(jg, "ultis_engage"):
        yield Conseil(
            "jungler-6", TEMPO, "Leur jungler est niveau 6.",
            "Gank avec ulti possible : reste du côté de ta vision.",
        )

    lane = s.en_lane(e)
    devant = avance_lane(e) >= NET  # en avance sur leur duo : un jungler seul ne suffit plus à te faire reculer
    if jg.mort and jg.reapparition >= 10 and not e.moi.mort:
        if ennemis_morts(e) >= 3:
            return  # la règle d'avantage numérique le dit déjà, en mieux
        if s.drake_dispo(e.t):
            yield Conseil(
                f"jungler-mort-{jg.morts}", TEMPO, f"Leur jungler est mort, {duree(jg.reapparition)}.",
                "Drake gratuit : ping ton jungler et pousse.", intention="objectif",
            )
        elif lane:
            yield Conseil(
                "jungler-mort", TEMPO, f"Leur jungler est mort, {duree(jg.reapparition)}.",
                "Personne ne viendra les aider : force le trade ou plonge avec la vague."
                if devant
                else "Tu peux pousser et warder sans risque.",
                repeter_apres=120, intention="agressif",
            )
        return

    if s.jungler_vu:
        t_vu, cote, indice = s.jungler_vu
        cle = f"jungler-vu-{cote}"  # un même côté n'est annoncé qu'une fois par minute (trois grubs = une annonce)
        traversee = j["traversee_carte"]
        if not s.jungler_vu_ce_tour:
            # Il s'était montré en haut : une fois le temps de traverser écoulé, la fenêtre se referme.
            if lane and cote == "top" and traversee <= e.t - t_vu < traversee + 20:
                yield Conseil(
                    f"jungler-fenetre-{int(t_vu)}", TEMPO, f"Leur jungler était top il y a {duree(traversee)}.",
                    "Il a eu le temps de descendre : un œil sur la rivière avant de plonger."
                    if devant
                    else "Ta fenêtre est finie, il a eu le temps de descendre. "
                    "Avancé : recule. Sous tour : c'est le moment de back.",
                    intention="" if devant else "prudent",
                )
        elif cote == "top" and s.drake_dispo(e.t):
            yield Conseil(
                cle, TEMPO, "Leur jungler vient d'apparaître en top.",
                "Il est loin : drake possible, ping ton jungler.", repeter_apres=60, intention="objectif",
            )
        elif cote == "top" and lane:
            yield Conseil(
                cle, TEMPO, "Leur jungler vient d'apparaître en top.",
                f"Tu es safe {traversee} secondes : joue agressif ou prends la vision rivière.", repeter_apres=60,
                intention="agressif",
            )
        elif cote == "mid" and lane and not devant:
            yield Conseil(
                cle, TEMPO, "Leur jungler vient d'apparaître mid.", "Il peut descendre vite. Avancé : recule.",
                repeter_apres=60, intention="prudent",
            )
        elif cote == "bot" and indice == "objectif" and lane:
            yield Conseil(
                cle, URGENT, "Leur jungler vient de prendre le drake, il est côté bot.",
                "Ils sont trois de ton côté : pas de plongée tant qu'il n'est pas reparti."
                if devant
                else "Avancé : recule, gank probable. Sous tour : c'est le moment de back.",
                repeter_apres=60, intention="prudent",
            )
        elif cote == "base" and lane and not devant:
            yield Conseil(
                cle, INFO, "Leur jungler est de retour en jeu.",
                f"Compte {j['base_vers_bot']} secondes avant qu'il puisse être bot.", repeter_apres=60,
            )

    sans_nouvelle = e.t - s.jungler_nouvelle
    if lane and sans_nouvelle >= c.seuils.jungler_inconnu and e.t - s.derniere_vision >= 60:
        depuis = "plus de 3 minutes" if sans_nouvelle > 180 else duree(round(sans_nouvelle / 15) * 15)
        if devant:
            # Devant, on ne recule pas : on pose la ward qui permet de continuer à presser.
            yield Conseil(
                "jungler-inconnu", INFO, f"Leur jungler n'a pas été vu depuis {depuis}.",
                f"Tu es devant, mais à trois ils te tuent : ward la rivière, puis continue de presser. "
                f"Il est à {score(jg)}.",
                repeter_apres=150,
            )
        else:
            yield Conseil(
                "jungler-inconnu", INFO, f"Leur jungler n'a pas été vu depuis {depuis}.",
                "Sans vision, ne dépasse pas le milieu de la lane.", repeter_apres=150, intention="prudent",
            )


def avantage(e: Etat, s: Suivi, c: Reglages) -> Iterator[Conseil]:
    morts = [j for j in e.ennemis if j.mort]

    if len(morts) >= 3 and not e.moi.mort:
        retour = min(j.reapparition for j in morts)  # le premier qui revient ferme la fenêtre
        if len(morts) == len(e.ennemis) and retour >= 20 and e.t >= 900:
            action = "Finissez : tout le monde mid avec la vague, la partie se gagne maintenant."
        elif s.baron_dispo(e.t) and retour >= 15:
            action = "Baron, maintenant."
        elif s.drake_dispo(e.t):
            action = "Drake, maintenant."
        else:
            action = "Prends une tour ou un inhibiteur : le back viendra après."
        yield Conseil(
            "avantage", URGENT, f"{len(morts)} ennemis morts.", action, repeter_apres=45, intention="objectif"
        )
        return

    if not s.en_lane(e):
        return
    support = e.allie("UTILITY")
    if support and support.mort and not e.moi.mort:
        marge = avance_lane(e)
        if marge >= ECRASANT:
            yield Conseil(
                f"support-mort-{support.morts}", TEMPO, "Ton support est mort.",
                f"Tu as {round(marge, -2):.0f} gold d'avance sur leur duo : garde ta vague et punis celui qui avance. "
                "Méfie-toi seulement de leur jungler.", intention="agressif",
            )
        elif marge >= NET:
            yield Conseil(
                f"support-mort-{support.morts}", TEMPO, "Ton support est mort.",
                "Tu es devant mais seul : farme, et ne prends que les trades à un contre un.",
            )
        else:
            yield Conseil(
                f"support-mort-{support.morts}", URGENT, "Ton support est mort.",
                "Tu es seul : recule sous ta tour et farm ce qui vient.", intention="prudent",
            )
    if e.moi.mort:
        return
    duo_mort = [j for j in morts if j.role in ROLES_BOT]
    # On ne commente qu'une mort qui vient d'arriver : pas celui qui reste mort quand l'autre réapparaît.
    if not any(e.t - s.morts_ennemies.get(j.nom, e.t) <= 3 for j in duo_mort):
        return
    drake = s.prochain_drake - e.t
    if len(duo_mort) == 2:
        if drake <= 60:
            action = "Crash la vague et enchaîne sur le drake : pas de back."
        elif drake <= 120 and or_en_poche(e) >= c.seuils.or_reset_objectif:
            action = "Crash la vague, back tout de suite, et reviens pour le drake avec tes objets."
        else:
            action = "Crash la vague et tape la tour, 120 gold la plaque, puis back."
        yield Conseil(
            f"duo-mort-{sum(j.morts for j in duo_mort)}", TEMPO, "Leur botlane est morte.", action, intention="objectif"
        )
    elif duo_mort[0].reapparition >= 12:
        j = duo_mort[0]
        role = "ADC" if j.role == "BOTTOM" else "support"
        yield Conseil(
            f"duo-mort-{j.nom}-{j.morts}", TEMPO, f"Leur {role} est mort, {duree(j.reapparition)}.",
            "Deux contre un : pousse, plaques, et plonge celui qui reste si la vague est grosse."
            if avance_lane(e) >= NET
            else "Deux contre un : pousse et mets la pression, sans dive.",
            intention="agressif",
        )


def farm(e: Etat, s: Suivi, c: Reglages) -> Iterator[Conseil]:
    for minute in (6, 10, 15, 20, 25):
        if minute * 60 <= e.t < minute * 60 + 30:
            rythme = s.cs_par_minute(e)
            if rythme >= c.seuils.cs_par_minute:
                action = "Bon rythme, continue."
            elif forme(e) == "domine":
                # Devant aux kills : le farm n'est pas la priorité, mais il reste de l'or facile.
                action = "Tu es devant aux kills : prends aussi les vagues entre deux combats, c'est de l'or sans risque."
            else:
                action = f"Sous l'objectif de {c.seuils.cs_par_minute:g}. Priorité au farm."
            lu = f"{rythme:.1f}".replace(".", ",")
            # Le jeu ne donne les sbires qu'à la dizaine près : on annonce le rythme, pas le compte.
            yield Conseil(f"farm-{minute}", INFO, f"{minute} minutes : environ {lu} sbires par minute.", action)


def items(e: Etat, s: Suivi, c: Reglages) -> Iterator[Conseil]:
    """Le rapport de force avec l'ADC adverse, et ce qu'il autorise."""
    adc = e.ennemi("BOTTOM")
    if adc is None or (s.nb_achats and e.t - s.dernier_achat < 20):
        return  # pas d'ADC en face, ou panier en cours : l'écart bouge à chaque clic
    ecart = e.moi.valeur_objets - adc.valeur_objets
    # Trois annonces au plus dans chaque sens : au-delà, l'écart est acquis et le redire n'apprend rien.
    palier = min(3, abs(ecart) // c.seuils.ecart_items)
    if palier == 0:
        return
    montant = round(abs(ecart) / 100) * 100
    if ecart < 0:
        yield Conseil(
            f"items-retard-{palier}", INFO, f"{adc.champion} a {montant} gold d'objets de plus que toi.",
            "Pas de trade long. Farm et attends ton prochain back.", intention="prudent",
        )
        return
    fait = f"Tu as {montant} gold d'objets d'avance sur {adc.champion} ({score(e.moi)} contre {score(adc)})."
    if palier == 1:
        action = "C'est ta fenêtre : force les trades."
    elif palier == 2:
        action = "Tu gagnes le un contre un : empêche-le d'approcher la vague, et punis chaque sbire qu'il prend."
    elif s.en_lane(e):
        action = "Tu peux te battre à un contre deux : plaques, plongée quand la vague est grosse, puis porte ton avance mid."
    else:
        action = "Tu le tues seul : cherche-le en combat, il ne peut pas te répondre."
    yield Conseil(f"items-avance-{palier}", TEMPO, fait, action, intention="agressif")


def tours(e: Etat, s: Suivi, c: Reglages) -> Iterator[Conseil]:
    for ev in s.nouveaux:
        structure = lire_structure(ev.cible) if ev.nom == "TurretKilled" else None
        if structure is None or structure[1] != "bot" or not structure[2]:
            continue  # seule la tour extérieure bot change le plan de l'ADC
        if structure[0] == e.moi.equipe:
            yield Conseil(
                "tour-bot-perdue", TEMPO, "Ta tour bot est tombée.",
                "La lane est trop longue : va farm mid, ne reste pas seul en bot.",
            )
        else:
            yield Conseil(
                "tour-bot-prise", TEMPO, "Tour bot ennemie détruite.",
                "Porte ton avance mid avec ton support : la tour mid est la suivante. La side, c'est pour ton toplaner."
                if forme(e) == "domine"
                else "Va mid avec ton support. La side, c'est pour ton toplaner.",
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
                f"{objet.sort} de {objet.champion} noté, retour "
                f"{'au plus tôt ' if objet.au_plus_tot else ''}à {heure(objet.retour)}.", action,
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
