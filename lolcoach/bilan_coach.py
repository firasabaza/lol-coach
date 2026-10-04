"""Le bilan d'une partie quand le client League n'en garde rien : outil d'entraînement, client fermé.

On le tire alors de ce que le coach a enregistré. Il manque ce que seul le client connaît, les
positions et les dégâts, donc pas de revue de carte. Tout le reste y est : les dix joueurs et leurs
objets, chaque mort avec ceux qui l'ont causée, les erreurs chiffrées, la courbe d'or.
"""

from __future__ import annotations

from .bilan import Bilan, Lecon, Moment, Participant, _liste, series_de_kills
from .datadragon import champions
from .etat import Etat, Joueur
from .moteur import Moteur
from .rapport import or_gagne
from .reglages import Reglages

MODES = {"PRACTICETOOL": "Outil d'entraînement", "CLASSIC": "Faille de l'invocateur"}


def _cle(j: Joueur) -> str:
    """La clé du champion telle que Data Dragon l'écrit : c'est elle qui nomme ses images."""
    return next((cle for cle in champions() if cle.lower() == j.cle.lower()), j.cle)


def _participant(numero: int, j: Joueur, moi: Joueur) -> Participant:
    est_moi = j.nom == moi.nom
    if j.role == "JUNGLE" or j.smite:
        role = "jungle"
    elif j.role == "UTILITY":
        role = "support"
    elif j.role == "BOTTOM" or est_moi:
        role = "adc"
    else:
        role = "solo"
    return Participant(
        id=numero, equipe=100 if j.equipe == "ORDER" else 200, cle=_cle(j), champion=j.champion, role=role,
        kills=j.kills, morts=j.morts, assists=j.assists, cs=j.cs, or_=j.valeur_objets, degats=0,
        vision=round(j.vision), pinks=-1, niveau=j.niveau, objets=[o.id for o in j.objets], moi=est_moi,
    )


def depuis_enregistrement(etats: list[Etat], victoire: bool | None, c: Reglages, identifiant: int, date: str) -> Bilan:
    """Rejoue les lectures enregistrées et en tire le bilan."""
    moteur = Moteur(c)
    moments: list[Moment] = []
    categories: list[str] = []
    images: list[dict] = []
    or_dormant = trou_vision = 0.0
    precedent: Etat | None = None
    kills_vus: list[float] = []

    dernier = etats[-1]
    numeros = {j.nom: n for n, j in enumerate(dernier.joueurs, start=1)}
    cles = {j.nom: _cle(j) for j in dernier.joueurs}

    for e in etats:
        moteur.lire(e)
        s = moteur.suivi
        adc = e.ennemi("BOTTOM")
        if precedent is not None and precedent.or_ >= c.seuils.or_recall and not precedent.moi.mort and not e.moi.build_complet:
            or_dormant += e.t - precedent.t
        if e.t > 120 and not e.moi.mort:
            trou_vision = max(trou_vision, e.t - s.derniere_vision)
        if not images or e.t - images[-1]["t"] >= 60:
            lui = max(adc.valeur_objets, 0.75 * or_gagne(adc, e.t)) if adc else 0
            images.append({"t": e.t, "positions": {}, "poche": {},
                           "or": {numeros[e.moi.nom]: round(e.moi.valeur_objets + e.or_),
                                  **({numeros[adc.nom]: round(lui)} if adc and adc.nom in numeros else {})}})

        if s.mort_ce_tour:
            fatal = next((ev for ev in reversed(e.evenements) if ev.victime == e.moi.nom), None)
            tueurs = [j for n in ([fatal.tueur, *fatal.assistants] if fatal else []) if (j := e.joueur(n))]
            analyse = f"Tué par {_liste([j.champion for j in tueurs])}." if tueurs else "Exécuté par une tour ou des sbires."
            if e.or_ >= c.seuils.or_recall:
                analyse += f" {round(e.or_)} gold en poche."
            lane = s.en_lane(e)
            if len(tueurs) >= 3:
                categorie = "inferiorite"
                conseil = f"À {len(tueurs)} sur toi, le combat était perdu : compte les présents avant d'avancer."
            elif lane and any(j.role == "JUNGLE" or j.smite for j in tueurs):
                categorie = "gank"
                conseil = "Gank subi : vague de ton côté tant que leur jungler n'a pas été vu, et ward rivière avant d'avancer."
            elif lane:
                categorie = "lane"
                conseil = "Trade perdu : avant de t'engager, compare niveaux, sbires et sorts. Deux avantages sur trois, sinon on farme."
            elif e.or_ >= c.seuils.or_recall:
                categorie = "riche"
                conseil = "Cet or devait être dépensé avant : back dès qu'il termine un objet, puis reviens te battre."
            else:
                categorie = "combat"
                conseil = "En combat, reste derrière ta frontline et tape la cible la plus proche : tu es mort avant de faire tes dégâts."
            titre = "Mort en phase de lane" if lane else "Mort en combat"
            moments.append(Moment(e.t, "mort", titre, analyse, conseil, 0, 0, [cles[j.nom] for j in tueurs if j.nom in cles]))
            categories.append(categorie)

        for ev in s.nouveaux:
            if ev.nom == "ChampionKill" and ev.tueur == e.moi.nom:
                kills_vus.append(e.t)
        precedent = e

    for t, nombre in series_de_kills(kills_vus):
        if nombre:
            moments.append(Moment(
                t, "exploit", f"{nombre} kills d'affilée",
                "Bon combat : tu es resté en vie assez longtemps pour faire tes dégâts.",
                "Retiens le placement de ce combat, c'est celui à refaire.", 0, 0,
            ))
    moments.sort(key=lambda m: m.t)

    joueurs = [_participant(numeros[j.nom], j, dernier.moi) for j in dernier.joueurs]
    moi = next(j for j in joueurs if j.moi)
    adversaire = next((j for j in joueurs if j.equipe != moi.equipe and j.role == "adc"), None)
    minutes = max(dernier.t / 60, 1)
    rythme = moteur.suivi.cs_par_minute(dernier)
    equipe = [j for j in joueurs if j.equipe == moi.equipe]
    a_14 = min(images, key=lambda i: abs(i["t"] - c.saison["sbires"]["fin_de_lane"]))
    ecart = a_14["or"].get(moi.id, 0) - a_14["or"].get(adversaire.id, 0) if adversaire and dernier.t >= 600 else 0

    lecons: list[Lecon] = []
    if rythme < c.seuils.cs_par_minute and dernier.t >= 360:
        manque = round((c.seuils.cs_par_minute - rythme) * minutes * 20, -2)
        lecons.append(Lecon(
            "Farm", f"{rythme:.1f} sbires par minute, pour un objectif de {c.seuils.cs_par_minute:g}.".replace(".", ",", 1),
            f"Environ {int(manque)} gold laissés sur la carte. Entre deux objectifs, il y a toujours une vague à prendre.",
            manque / 300,
        ))
    if or_dormant >= 60:
        lecons.append(Lecon(
            "Recalls trop tardifs", f"{round(or_dormant / 60, 1):g} minutes jouées avec plus de {c.seuils.or_recall} gold en poche.".replace(".", ",", 1),
            "Back dès que ton or termine un objet : se battre avec l'objet vaut mieux que mourir avec l'or.",
            or_dormant / 25,
        ))
    if trou_vision >= c.seuils.vision_silence:
        lecons.append(Lecon(
            "Vision", f"Jusqu'à {round(trou_vision / 60, 1):g} minutes sans rien poser.".replace(".", ",", 1),
            "Trinket dès qu'il est disponible, et une pink à chaque back tant qu'il reste une place.", trou_vision / 45,
        ))
    for categorie, titre, constat, conseil, poids in (
        ("inferiorite", "Combats perdus d'avance", "tué par trois ennemis ou plus",
         "Compte les présents avant chaque combat. S'il manque deux alliés, on recule et on cède.", 5),
        ("lane", "Morts en lane", "sur un trade perdu en phase de lane",
         "La vague décide : de ton côté quand tu es en retard, sans vision ou sans support. On trade avec deux avantages.", 4),
        ("gank", "Ganks subis", "sur un gank en phase de lane",
         "Vague de ton côté tant que leur jungler n'est pas vu, et ward rivière avant de dépasser le milieu.", 4),
        ("riche", "Morts avec l'or en poche", f"avec plus de {c.seuils.or_recall} gold non dépensés",
         "Cet or était un objet de plus dans le combat : back avant, bats-toi après.", 4),
        ("combat", "Placement en combat", "en plein combat",
         "Derrière ta frontline, la cible la plus proche d'abord. Mort, tu ne fais plus aucun dégât.", 3),
    ):
        n = categories.count(categorie)
        if n >= 2 or (n == 1 and moi.morts <= 3):
            lecons.append(Lecon(titre, f"{n} de tes {moi.morts} morts : {constat}.", conseil, poids * n))
    lecons.sort(key=lambda lecon: -lecon.poids)

    points_forts = []
    if rythme >= c.seuils.cs_par_minute:
        points_forts.append(f"Farm solide : {rythme:.1f} sbires par minute.".replace(".", ",", 1))
    if moi.morts <= 3 and dernier.t >= 600:
        points_forts.append(f"{moi.morts} mort{'s' if moi.morts > 1 else ''} seulement.")
    if adversaire and ecart >= 600:
        points_forts.append(f"Lane gagnée : environ {round(ecart, -2)} gold d'avance sur {adversaire.champion} à 14 minutes.")

    return Bilan(
        identifiant=identifiant, file=MODES.get(dernier.mode, "Partie"), date=date, duree=round(dernier.t),
        victoire=victoire, joueurs=joueurs, moi=moi, adversaire=adversaire, moments=moments, lecons=lecons[:4],
        points_forts=points_forts[:3], images=images, kills=[], objectifs=[],
        chiffres={
            "cs_par_minute": rythme,
            "participation": (moi.kills + moi.assists) / (sum(j.kills for j in equipe) or 1),
            "vision_par_minute": moi.vision / minutes,
            "ecart_or_14": ecart,
        },
        source="coach",
    )
