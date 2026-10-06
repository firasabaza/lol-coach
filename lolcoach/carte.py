"""Où aller et quoi prendre : une seule décision, tirée de l'état du joueur et de la carte.

Le coach ne voit pas les positions : l'API du jeu ne les donne pas. Il connaît les tours debout,
les morts et l'heure de leur retour, l'horloge des objectifs, les PV et l'or du joueur. C'est assez
pour trancher entre un back, un objectif et une tour, et pour dire quelle lane est la plus sûre.
Ce qui se passe sur la lane elle-même (un allié qui farme déjà la vague, un ennemi qui la tient),
seul le joueur le voit : il redemande, et le coach propose la solution suivante.
"""

from __future__ import annotations

from dataclasses import dataclass

from .achats import a_la_boutique, finissable
from .etat import Etat
from .mots import duree
from .rapport import drake_jouable, forme, or_en_poche, vivants
from .reglages import Reglages
from .suivi import Suivi

PV_POUR_JOUER = 0.40  # en dessous, on ne prend ni tour ni objectif : on rentre
PROCHE = 75  # secondes : un objectif plus proche que ça décide de l'endroit où être
TROP_TARD = 15  # secondes : si les morts sont de retour en lane plus vite, il n'y a plus de fenêtre à jouer
POUR_UNE_PLAQUE = 25  # secondes qu'il faut avoir devant soi pour aller taper une tour


@dataclass(frozen=True)
class Decision:
    quoi: str  # « back », « objectif », « tour » ou « fin »
    phrase: str


@dataclass(frozen=True)
class Direction:
    cle: str  # « nombre », « back », « objectif », « mid », « side »... : une réponse par clé et par demande
    phrase: str


def _pourcent(pv: float) -> str:
    return f"{round(pv * 100)} %"


def tour_a_prendre(e: Etat, s: Suivi, c: Reglages) -> str | None:
    """La structure adverse à viser, par son nom : « la tour mid extérieure », « l'inhibiteur bot »."""
    eux = "CHAOS" if e.moi.equipe == "ORDER" else "ORDER"
    lanes = ("bot", "mid", "top") if s.en_lane(e) else ("mid", "bot", "top")
    # Un inhibiteur à découvert passe avant une tour : c'est lui qui ouvre la base.
    for lane in lanes:
        if s.tours_tombees.get((eux, lane), 0) >= 3 and (eux, lane) not in s.inhibiteurs:
            return f"l'inhibiteur {lane}"
    for lane in lanes:
        tombees = s.tours_tombees.get((eux, lane), 0)
        if tombees == 0:
            return f"la tour {lane} extérieure"  # la seule qui porte des plaques, et elles restent toute la partie
        if tombees < 3:
            return f"la tour {lane} intérieure" if tombees == 1 else f"la tour d'inhibiteur {lane}"
    return None


def prochain_objectif(e: Etat, s: Suivi, c: Reglages) -> tuple[str, float, str]:
    """(nom, secondes avant qu'il soit là, côté de la carte) du prochain objectif neutre."""
    o = c.saison["objectifs"]
    candidats = [("Elder" if s.elder else "Drake", s.prochain_drake, "bot"), ("Baron", s.prochain_baron, "top")]
    # Le Herald ne compte qu'autour de son apparition : resté là trois minutes, plus personne ne le joue.
    if not s.herald_pris and e.t < o["herald"] + 45:
        candidats.append(("Herald", float(o["herald"]), "top"))
    nom, quand, cote = min(candidats, key=lambda candidat: candidat[1])
    return nom, max(0.0, quand - e.t), cote


def apres_combat(e: Etat, s: Suivi, c: Reglages) -> Decision | None:
    """Des ennemis sont morts : back, objectif ou tour, selon ce que le joueur peut encore faire.

    None quand ils reviennent trop vite pour qu'il reste quelque chose à jouer.
    """
    morts = [j for j in e.ennemis if j.mort]
    retour = min(j.reapparition for j in morts)  # le premier qui revient ferme la fenêtre
    # Avec le homeguard, un mort qui réapparaît est en lane mid douze secondes plus tard.
    en_lane = retour + c.saison["trajets"]["base_vers_mid"]
    nous, eux = vivants(e)
    poche = or_en_poche(e)
    achat = a_la_boutique(e, poche)
    riche = poche >= c.seuils.or_recall or finissable(e, poche) is not None
    boutique = f" À la boutique : {achat}." if achat else ""
    jungler = e.allie("JUNGLE")
    smite = jungler is not None and not jungler.mort
    nom, dans, _ = prochain_objectif(e, s, c)

    if len(morts) == len(e.ennemis) and retour >= 20 and e.t >= 900:
        # Plus personne en face : les PV ne comptent plus.
        return Decision("fin", "Finissez : tout le monde mid avec la vague, la partie se gagne maintenant.")
    if e.pv <= PV_POUR_JOUER:
        # Bas en PV, on ne prend rien : mais c'est le moment le plus sûr de la partie pour rentrer.
        suite = f" Tu reviens pour le {nom}." if dans <= 60 else ""
        return Decision("back", f"Tu es à {_pourcent(e.pv)} : c'est le moment le plus sûr pour rentrer. "
                                f"Back maintenant.{boutique}{suite}")
    if en_lane < TROP_TARD:
        return None
    if s.baron_dispo(e.t) and retour >= 15 and nous >= 4 and smite:
        return Decision("objectif", f"Baron, maintenant : ils ne sont plus que {eux}.")
    if s.drake_dispo(e.t) and retour >= 10 and (smite or nous >= 3):
        return Decision("objectif", "Drake, maintenant." if smite else "Drake, maintenant : sans ton jungler, tout le monde dessus.")
    tour = tour_a_prendre(e, s, c)
    if riche and (en_lane < POUR_UNE_PLAQUE or tour is None):
        return Decision("back", f"Ils sont de retour en lane dans {duree(en_lane)} : pas le temps pour une tour. "
                                f"Back maintenant.{boutique}")
    if tour is None:
        return Decision("tour", "Pousse la vague la plus proche avec ton équipe.")
    apres = f" Back juste après : tu as {int(poche // 50 * 50)} gold à dépenser." if riche else ""
    # Une tour extérieure se prend en deux ou trois passages : elle durcit vingt secondes après chaque plaque.
    plaques = " Une ou deux plaques à 120 gold, pas plus : elle durcit après chacune." if tour.endswith("extérieure") else ""
    return Decision("tour", f"{tour[0].upper()}{tour[1:]}, avec la vague.{plaques}{apres}")


def _mid(e: Etat, s: Suivi, etat: str) -> str:
    tombees = s.tours_tombees.get((e.moi.equipe, "mid"), 0)
    if tombees == 0 and etat == "domine":
        return "Mid avec ton support : pousse la vague et tape la tour. Recule dès que trois ennemis disparaissent de la carte."
    if tombees == 0:
        phrase = ("Mid : c'est la lane la plus courte, ta tour est à deux pas. "
                  "Pousse seulement avec ton support, ou quand tu vois leur jungler ailleurs.")
    elif tombees == 1:
        phrase = "Mid, devant ta tour intérieure : laisse la vague venir à toi, pas plus loin que l'ancienne tour sans vision."
    else:
        phrase = "Mid, sous ta tour d'inhibiteur : nettoie la vague de loin et reste collé à ton équipe."
    return f"Reste avec ton support. {phrase}" if etat == "retard" else phrase


def _side(e: Etat, s: Suivi, cote: str) -> str:
    tombees = s.tours_tombees.get((e.moi.equipe, cote), 0)
    if tombees == 0:
        return f"La vague {cote} quand elle arrive à ta tour extérieure, puis retour mid : pas plus de quinze secondes seul."
    if tombees == 1:
        return (f"La vague {cote} devant ta tour intérieure seulement, et pas sans voir trois ennemis ailleurs sur la carte. "
                "Retour mid tout de suite après.")
    return f"Plus de tour en {cote} : n'y va pas seul. Attends que la vague arrive à ta base, ou vas-y avec ton équipe."


def directions(e: Etat, s: Suivi, c: Reglages) -> list[Direction]:
    """Où aller maintenant : le meilleur choix d'abord, puis les solutions de repli."""
    choix: list[Direction] = []
    poche = or_en_poche(e)
    nous, eux = vivants(e)
    # Deux de plus qu'eux : la même décision que pour un combat gagné, PV et or compris.
    occasion = apres_combat(e, s, c) if nous - eux >= 2 and not e.moi.mort else None
    if occasion:
        choix.append(Direction("nombre", f"Ils ne sont plus que {eux}. {occasion.phrase}"))
    elif not e.moi.mort and e.pv <= PV_POUR_JOUER:
        achat = a_la_boutique(e, poche)
        boutique = f" À la boutique : {achat}." if achat else ""
        choix.append(Direction("back", f"Tu es à {_pourcent(e.pv)} : back d'abord.{boutique}"))

    if s.en_lane(e):
        drake = s.prochain_drake - e.t
        choix.append(Direction(
            "lane",
            "Reste bot : pousse ta vague, puis rivière côté drake avec ton support."
            if drake <= 60
            else "Reste bot : ta vague d'abord, et pas plus loin que le milieu de la lane sans vision de la rivière.",
        ))
        choix.append(Direction("sous-tour", "Si la lane est injouable, recule sous ta tour et laisse venir la vague : "
                                            "trois sbires perdus valent mieux qu'une mort."))
        choix.append(Direction("plaques-mid", "Si ta vague est poussée et que rien ne se passe en bot, monte mid avec ton "
                                              "support pour les plaques, et redescends pour la vague suivante."))
        return choix

    etat = forme(e)
    nom, dans, cote = prochain_objectif(e, s, c)
    if nous < eux:
        retour = min((j.reapparition for j in e.allies if j.mort and j.nom != e.moi.nom), default=0)
        attente = f"Pas de combat avant le retour de tes alliés, {duree(retour)}." if retour >= 5 else "Tes alliés reviennent : attends-les."
        choix.append(Direction("nombre", f"À {nous} contre {eux} : sous ta tour mid, nettoie la vague de loin. {attente}"))
    # Un objectif qui arrive, ou qui est là et qu'on peut jouer (jungler en vie, pas en infériorité).
    if 0 < dans <= PROCHE or (dans == 0 and drake_jouable(e)):
        quand = f"dans {duree(round(dans / 5) * 5)}" if dans > 5 else "disponible"
        conduite = ("Reste derrière ton équipe et ne conteste que si elle y va"
                    if etat == "retard" or nous < eux
                    else "Arrive avec ton équipe, jamais le premier dans la rivière")
        choix.append(Direction("objectif", f"{nom} {quand} : passe par mid, puis côté {cote}. {conduite}."))
    choix.append(Direction("mid", _mid(e, s, etat)))
    # Mid à trois sur une vague, c'est de l'or perdu pour le rôle qui en gagne le plus par sbire.
    choix.append(Direction("vagues", "Si un allié farme déjà mid, ne partage pas : regarde les trois vagues et va à la "
                                     "plus grosse. Pousse-la tant que c'est sûr, puis regroupe."))
    choix.append(Direction("side", _side(e, s, cote)))
    choix.append(Direction("jungle", f"Aucune vague libre : prends les camps de ta jungle côté {cote} s'ils sont là, "
                                     "puis la vague suivante."))
    return choix
