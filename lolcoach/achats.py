"""Quel objet acheter maintenant : la suite du build du champion, ou ce que la partie impose.

Le conseil se recalcule à chaque lecture. Il suit ce que font les ennemis (qui est nourri, qui
empile les résistances, qui soigne, d'où viennent leurs dégâts), l'état du joueur et ce que son
équipe lui offre. Plus le build avance, plus tôt un besoin de la partie passe devant le build type.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .compo import (
    PLONGEURS, chemin, classe, composants_manquants, est, famille_de_build, fiche, lire_compo, nom_objet, noms,
    objets_finis, premiers, reste_a_payer, suite,
)
from .datadragon import objets
from .etat import PRIX_OBJET_FINI, Etat, Joueur
from .rapport import NET, avance, avance_lane, forme, puissance, score

UTILE = 2.0  # en dessous, un besoin ne vaut pas un emplacement
# Score à partir duquel un besoin passe devant le build, selon le nombre d'objets finis. Sans
# premier objet, rien ne passe devant : un carry sans dégâts ne sert à rien, même vivant.
SEUILS = {1: 4.0, 2: 3.0}

_TIREUR = {
    "anti_controle": (3139, 3140),  # Cimeterre mercuriel, par la Ceinture de mercure
    "anti_soin": (3033, 3123),  # Rappel mortel, par la Marque du bourreau
    "anti_armure": (3036, 3035),  # Salutations de Dominik, par le Dernier souffle
    "survie_ad": (6673, None),  # Arc-bouclier immortel : il garde le critique
    "survie_ap": (6673, None),
}
# Besoin -> (objet, composant pas cher à prendre en attendant), par famille de build.
OBJETS: dict[str, dict[str, tuple[int, int | None]]] = {
    "adc": _TIREUR,
    "on_hit": _TIREUR | {"survie_ad": (3026, None), "survie_ap": (3091, None)},  # Ange gardien, Au bout du rouleau
    "kaisa": {
        "anti_controle": (3140, None),  # la Ceinture suffit : le Cimeterre n'apporte rien à un build hybride
        "anti_rm": (3135, None),  # Bâton du vide
        "survie_ad": (3157, 2420),  # Sablier de Zhonya, par le Protège-bras du savant
        "survie_ap": (3091, None),
    },
    "mage": {
        "anti_controle": (3140, None),
        "anti_soin": (3165, 3916),  # Morellonomicon, par l'Orbe de l'oubli
        "anti_rm": (3135, None),
        "survie_ad": (3157, 2420),
        "survie_ap": (3102, None),  # Voile de la banshee
    },
}
BOTTES = {"mage": 3020}  # Chaussures de sorcier ; Jambières du berzerker pour les autres
# Objets au même passif unique : on n'en porte qu'un par groupe.
EXCLUSIFS = ({3033, 3036, 6694}, {6673, 3156, 3053})
EMPLACEMENTS = 6  # objets finis hors bottes : la quête de rôle range les bottes dans un septième emplacement
# Objets de transition des tireurs (vitesse d'attaque et critique) : bons devant, à sauter derrière.
TRANSITION = {3046, 3094, 3085, 6675}
SUR_COUPS = ("on_hit", "kaisa")  # builds où la vitesse d'attaque vaut autant que les dégâts dès le début


@dataclass(frozen=True)
class Achat:
    objet: int
    raison: str
    composant: int | None = None  # ce qu'on peut prendre tout de suite quand l'objet est trop cher
    score: float = 0.0  # 0 : simple suite du build
    devance: int | None = None  # l'objet du build type que celui-ci fait passer après


def famille(j: Joueur) -> str:
    nom = famille_de_build(j)
    if nom in OBJETS:
        return nom
    return "mage" if fiche(j).get("degats") == "AP" else "adc"


def _somme(j: Joueur, cle: str) -> float:
    return sum(objets().get(o.id, {}).get(cle, 0) for o in j.objets)


def _porte(j: Joueur, etiquette: str, prix: int = PRIX_OBJET_FINI) -> bool:
    """Le joueur a-t-il un objet de ce genre, d'au moins ce prix ?"""
    return any(o.prix >= prix and etiquette in objets().get(o.id, {}).get("etiquettes", []) for o in j.objets)


def _sac(j: Joueur) -> list[int]:
    """L'inventaire, un identifiant par exemplaire. Les bottes offertes par la rune se montent comme des Bottes."""
    return [1001 if o.id == 2422 else o.id for o in j.objets for _ in range(o.nombre)]


def _groupe(objet: int) -> set[int]:
    return next((groupe for groupe in EXCLUSIFS if objet in groupe), {objet})


def tempo_adverse(e: Etat) -> tuple[str, list[Joueur]]:
    """La compo d'en face veut-elle tuer vite (« rush ») ou faire durer (« defense ») ?

    Les tops sont presque toujours des combattants, les junglers des bruisers, les ADC des tireurs :
    ce sont le mid et le support qui donnent le ton. Vide quand ils ne disent pas la même chose.
    """
    duo = [j for j in (e.ennemi("MIDDLE"), e.ennemi("UTILITY")) if j]
    if len(duo) < 2:
        return "", []
    mid, sup = duo
    if est(mid, "mids_assassins") and (est(sup, "engages") or est(sup, "accroches")):
        return "rush", duo
    if est(mid, "mids_de_controle") and classe(sup, {"ENCHANTER"}):
        return "defense", duo
    return "", []


def besoins(e: Etat) -> list[tuple[str, float, str]]:
    """Ce que la partie réclame en ce moment : (besoin, score, raison), du plus pressant au moins pressant."""
    compo = lire_compo(e)
    magique = fiche(e.moi).get("degats") == "AP"
    liste: list[tuple[str, float, str]] = []

    # Un sort qui te sort du combat : d'autant plus grave que celui qui le lance peut te tuer derrière.
    if compo.suppressions:
        verbe = "te sortent" if len(compo.suppressions) > 1 else "te sort"
        forme = max(j.kills - j.morts for j in compo.suppressions)
        poids = 3.0 + min(1.5, max(0, forme) * 0.4) + 0.5 * (len(compo.suppressions) > 1)
        liste.append(("anti_controle", poids, f"{noms(compo.suppressions)} {verbe} du combat d'un seul sort"))

    # Ceux qui viennent te chercher, pesés par ce qu'ils valent maintenant et par ce qui te protège.
    chasseurs = [j for j in e.ennemis if classe(j, PLONGEURS) or classe(j, {"BURST"})]
    dangereux = [j for j in chasseurs if j.kills - j.morts >= 2 or avance(e, j) <= -NET]
    prime = e.moi.kills - e.moi.morts >= 4
    seul = not any(classe(j, {"ENCHANTER", "WARDEN"}) for j in e.allies if j.nom != e.moi.nom)
    tempo, meneurs = tempo_adverse(e)
    for cle, groupe in (("survie_ad", [j for j in dangereux if j in compo.ad]),
                        ("survie_ap", [j for j in dangereux if j in compo.ap])):
        if groupe:
            pire = max(groupe, key=lambda j: puissance(e, j))
            poids = 3.0 + min(2.0, max(0, pire.kills - pire.morts) * 0.4) + 0.5 * (len(groupe) > 1) + 0.5 * prime
            raison = f"{pire.champion} est à {score(pire)} et vient sur toi"
            if prime:
                raison += ", et tu portes une prime"
            elif seul:
                poids += 0.5
                raison += ", et personne ne te protège"
            # Une compo qui tue vite rend la survie plus rentable ; une compo qui dure se bat aux dégâts.
            poids += 0.5 if tempo == "rush" else -0.5 if tempo == "defense" else 0
            liste.append((cle, poids, raison))
    if not dangereux and tempo == "rush":
        cle = "survie_ad" if meneurs[0] in compo.ad else "survie_ap"
        liste.append((cle, 3.0, f"{noms(meneurs)} veulent te tuer avant que tu tapes"))
    elif len(chasseurs) >= 3 and not dangereux and tempo != "defense":
        cle = "survie_ad" if sum(j in compo.ad for j in chasseurs) >= 2 else "survie_ap"
        liste.append((cle, 2.5, f"{noms(chasseurs)} viennent sur toi"))

    # Les soins : un soigneur seul attend la fin du build, trois passent devant. Un soigneur nourri pèse plus.
    soigneurs = list(compo.soigneurs) + [j for j in e.ennemis if j not in compo.soigneurs and _porte(j, "LifeSteal")
                                         and j.kills - j.morts >= 2]
    if soigneurs:
        nourris = sum(j.kills - j.morts >= 2 for j in soigneurs)
        liste.append(("anti_soin", min(1.0 + len(soigneurs) + 0.5 * nourris, 4.5), f"soins de {noms(soigneurs)}"))

    # Leurs résistances : on répond à ce qu'ils ont acheté, pas à ce qu'ils pourraient acheter.
    cle, mesure, seuil = ("anti_rm", "rm", 60) if magique else ("anti_armure", "armure", 90)
    blindes = [j for j in e.ennemis if _somme(j, mesure) >= seuil]
    if blindes:
        quoi = "de la résistance magique" if magique else "de l'armure"
        accord = "ont" if len(blindes) > 1 else "a"
        liste.append((cle, min(2.5 + len(blindes), 4.5), f"{noms(blindes)} {accord} acheté {quoi}"))
    elif len(compo.tanks) >= 2:
        liste.append((cle, 2.5, f"{len(compo.tanks)} tanks en face"))

    return sorted(liste, key=lambda besoin: -besoin[1])


def conseils(e: Etat) -> list[Achat]:
    """Les objets que la partie justifie et que tu n'as pas encore, du plus pressant au moins pressant."""
    table = OBJETS[famille(e.moi)]
    retenus: dict[int, Achat] = {}
    for besoin, poids, raison in besoins(e):
        objet, composant = table.get(besoin, (None, None))
        if objet is None or objet in retenus or any(e.moi.possede(i) for i in _groupe(objet)):
            continue
        attente = composant if composant and not e.moi.possede(composant) else None
        retenus[objet] = Achat(objet, raison, attente, poids)
    # Rappel mortel et Salutations de Dominik ne se cumulent pas : face aux soins et à l'armure, le premier fait les deux.
    if 3033 in retenus and 3036 in retenus:
        soin, armure = retenus[3033], retenus.pop(3036)
        retenus[3033] = replace(soin, raison=f"{soin.raison}, et {armure.raison}", score=max(soin.score, armure.score) + 0.5)
    return sorted(retenus.values(), key=lambda achat: -achat.score)


def bottes(e: Etat) -> Achat:
    """Les bottes à finir : celles du champion, sauf si la compo adverse en impose d'autres."""
    compo = lire_compo(e)
    tueurs = [j for j in compo.plongeurs if j in compo.ad]
    if len(compo.controles) >= 3:
        return Achat(3111, f"{len(compo.controles)} contrôles longs en face", score=2.5)
    if len(compo.ad) >= 4 and tueurs:
        return Achat(3047, f"{len(compo.ad)} champions à dégâts physiques, dont {noms(tueurs)}", score=2.5)
    return Achat(BOTTES.get(famille(e.moi), 3006), "c'est le moment de finir tes bottes")


def _chemin(e: Etat) -> list[int]:
    """Le build type, avec pour premier objet celui que le joueur est vraiment en train de monter."""
    moi = e.moi
    etapes = chemin(moi)
    if not etapes or moi.possede(etapes[0]):
        return etapes
    sac = _sac(moi)
    table = objets()

    def avancement(objet: int) -> int:
        return table.get(objet, {}).get("prix", 0) - reste_a_payer(objet, sac)

    # À égalité, max garde le premier de la liste : l'objet par défaut de la famille.
    return [max([etapes[0], *premiers(moi)], key=avancement), *etapes[1:]]


def _build(e: Etat, situation: list[Achat]) -> list[Achat]:
    """Ce qu'il reste du build type, dans la limite des emplacements libres."""
    moi = e.moi
    reste = []
    for objet in _chemin(e) + suite(moi):
        groupe = _groupe(objet) - {objet}
        if moi.possede(objet) or any(moi.possede(i) for i in groupe):
            continue
        # Un objet du chemin cède sa place à celui du même groupe que la partie réclame.
        reste.append(next((a for a in situation if a.objet in groupe), Achat(objet, "c'est la suite de ton build")))
    # En retard, ou avec deux besoins sérieux à caser : l'objet de transition attend. Il ralentit
    # l'arrivée des objets qui te permettent de faire des dégâts à des ennemis déjà plus solides.
    presse = forme(e) == "retard" or avance_lane(e) <= -NET or sum(a.score >= 3.0 for a in situation) >= 2
    if presse and objets_finis(moi) and reste and reste[0].objet in TRANSITION:
        reste = [a for a in reste if a.objet not in TRANSITION] + [a for a in reste if a.objet in TRANSITION]
        if reste[0].score == 0:
            reste[0] = replace(reste[0], raison="tu es en retard : va droit aux objets qui percent, la vitesse d'attaque attendra")
    # Un objet pris hors du chemin occupe un emplacement : c'est la fin de la liste qui saute, pas le cœur du build.
    return reste[: max(0, EMPLACEMENTS - objets_finis(moi))]


def prochain(e: Etat) -> Achat | None:
    """L'objet à viser maintenant."""
    moi = e.moi
    situation = conseils(e)
    build = _build(e, situation)
    coeur = build[0].objet if build and build[0].objet in _chemin(e) else None  # le build type n'est pas fini
    # Tant qu'il l'est pas, un objet de situation par objet de dégâts : deux d'affilée et tu ne tues plus rien.
    de_situation = {objet for objet, _ in OBJETS[famille(moi)].values()} - set(_chemin(e))
    pris = sum(o.prix >= PRIX_OBJET_FINI and o.id in de_situation for o in moi.objets)
    finis = objets_finis(moi) - pris
    if finis and situation and situation[0].score >= SEUILS.get(finis, UTILE) and (coeur is None or pris < finis):
        return replace(situation[0], devance=coeur)
    if finis and not _porte(moi, "Boots", prix=900):  # 900 : les bottes de base ne comptent pas
        return bottes(e)
    if build:
        return build[0]
    return situation[0] if situation and situation[0].score >= UTILE else None


def finissable(e: Etat, poche: float) -> int | None:
    """L'objet que l'or en poche permet de terminer tout de suite, s'il y en a un."""
    vise = prochain(e)
    if vise is None or objets().get(vise.objet, {}).get("prix", 0) < PRIX_OBJET_FINI:
        return None
    return vise.objet if 0 < reste_a_payer(vise.objet, _sac(e.moi)) <= poche else None


def _valeur_tot(composant: int, sur_coups: bool) -> tuple[bool, int]:
    """Ce qu'un composant apporte en début de partie : les dégâts purs d'abord, puis le prix.

    Un trade de lane, c'est une ou deux autos et un sort : les dégâts d'attaque servent à chaque
    coup, la vitesse d'attaque seulement si le combat dure. Sauf pour les builds à effets à l'impact.
    """
    fiche_objet = objets().get(composant, {})
    genres = fiche_objet.get("etiquettes", [])
    return ("Damage" in genres and "AttackSpeed" not in genres) or sur_coups, fiche_objet.get("prix", 0)


def bon_back(e: Etat, defaut: int) -> int:
    """L'or à partir duquel un back vaut le coup : de quoi payer le composant qui compte pour l'objet visé."""
    vise = prochain(e)
    if vise is None:
        return defaut
    sac = _sac(e.moi)
    sur_coups = famille_de_build(e.moi) in SUR_COUPS
    gros = [c for c in composants_manquants(vise.objet, sac) if _valeur_tot(c, sur_coups)[1] >= 750]
    purs = [c for c in gros if _valeur_tot(c, sur_coups)[0]] or gros
    return min(defaut, max(875, min(_valeur_tot(c, sur_coups)[1] for c in purs))) if purs else defaut


def a_la_boutique(e: Etat, poche: float) -> str | None:
    """Quoi acheter avec l'or en poche pour avancer vers l'objet visé. None s'il n'y a rien à conseiller."""
    vise = prochain(e)
    if vise is None:
        return None
    table = objets()
    sac = _sac(e.moi)

    def prix(objet: int) -> int:
        return table.get(objet, {}).get("prix", 0)

    reste = reste_a_payer(vise.objet, sac)
    if reste <= poche:
        return f"{'finis' if prix(vise.objet) >= PRIX_OBJET_FINI else 'prends'} {nom_objet(vise.objet)}"
    if vise.composant:
        # Le composant fait déjà le travail (l'anti-soin, la Ceinture) : c'est lui qu'on veut, pas un autre.
        if prix(vise.composant) <= poche:
            return f"{nom_objet(vise.composant)} tout de suite, {nom_objet(vise.objet)} ensuite"
        cible, manque = vise.composant, prix(vise.composant) - poche
    else:
        # Sinon, le composant qui sert le plus tout de suite, à n'importe quel étage de la recette.
        sur_coups = famille_de_build(e.moi) in SUR_COUPS
        abordables = [c for c in composants_manquants(vise.objet, sac) if reste_a_payer(c, sac) <= poche]
        if abordables:
            choix = max(abordables, key=lambda c: _valeur_tot(c, sur_coups))
            return f"{nom_objet(choix)}, en route vers {nom_objet(vise.objet)}"
        cible, manque = vise.objet, reste - poche
    if poche < 600:
        return None  # rien à acheter : inutile d'en parler
    return f"garde ton or pour {nom_objet(cible)}, il manque {round(manque, -1):.0f} gold"
