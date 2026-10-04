"""Analyse d'une partie terminée, à partir de ce que le client League en garde.

Entrées : la partie (stats finales des dix joueurs) et sa chronologie (position et or de chacun
toutes les minutes, lieu exact de chaque kill, objectif et tour). Sortie : un Bilan prêt à afficher,
avec les moments clés et ce qu'il y a à améliorer. Tout est pur : rien n'est lu ni écrit ici.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import dist

from .datadragon import champion_par_id
from .reglages import Reglages

CARTE = (-120.0, -120.0, 14870.0, 14980.0)  # coins de la carte, en coordonnées du jeu
DRAKE, BARON = (9866.0, 4414.0), (5007.0, 10471.0)
SMITE = 11
A_PORTEE = 2500  # distance à laquelle un allié peut encore aider
PRESENT = 2500  # distance à un objectif pour compter comme présent (la botlane est à 3500 du drake)
FILES = {420: "Classée solo", 440: "Classée flexible", 400: "Normale", 430: "Normale", 480: "Swiftplay",
         490: "Partie rapide", 450: "ARAM", 0: "Partie personnalisée", 3140: "Outil d'entraînement"}
MONSTRES = {"DRAGON": "Drake", "BARON_NASHOR": "Baron", "RIFTHERALD": "Herald", "HORDE": "Grubs"}


@dataclass
class Participant:
    id: int
    equipe: int  # 100 (bleu) ou 200 (rouge)
    cle: str
    champion: str
    role: str  # "jungle", "adc", "support" ou "solo"
    kills: int
    morts: int
    assists: int
    cs: int
    or_: int
    degats: int
    vision: int
    pinks: int
    niveau: int
    objets: list[int]
    moi: bool = False


@dataclass
class Moment:
    t: float
    genre: str  # "mort", "exploit" ou "objectif"
    titre: str
    analyse: str
    conseil: str
    x: float
    y: float
    acteurs: list[str] = field(default_factory=list)  # clés des champions en cause


@dataclass
class Lecon:
    titre: str
    constat: str
    conseil: str
    poids: float


@dataclass
class Bilan:
    identifiant: int
    file: str
    date: str
    duree: int
    victoire: bool | None  # None : partie quittée sans résultat (outil d'entraînement)
    joueurs: list[Participant]
    moi: Participant
    adversaire: Participant | None  # leur ADC
    moments: list[Moment]
    lecons: list[Lecon]
    points_forts: list[str]
    images: list[dict]  # par minute : {"t": secondes, "positions": {id: [x, y]}, "or": {id: total}}
    kills: list[dict]  # {"t", "x", "y", "tueur", "victime"}
    objectifs: list[dict]  # {"t", "x", "y", "nom", "equipe"}
    chiffres: dict[str, float]  # cs_par_minute, part_degats, participation, presence, vision_par_minute, ecart_or_14
    source: str = "client"  # "client" : client League (tout) ; "coach" : enregistrement du coach (sans carte)


def _participants(partie: dict, puuid: str) -> list[Participant]:
    mien = next((i["participantId"] for i in partie["participantIdentities"] if i["player"].get("puuid") == puuid), -1)
    joueurs = []
    for p in partie["participants"]:
        s, ligne = p["stats"], p.get("timeline", {})
        cle, fiche = champion_par_id(p["championId"])
        if SMITE in (p.get("spell1Id"), p.get("spell2Id")):
            role = "jungle"
        elif ligne.get("lane") == "BOTTOM" and "SUPPORT" in ligne.get("role", ""):
            role = "support"
        elif ligne.get("lane") == "BOTTOM":
            role = "adc"
        else:
            role = "solo"
        joueurs.append(Participant(
            id=p["participantId"], equipe=p["teamId"], cle=cle, champion=fiche.get("nom", f"Champion {p['championId']}"),
            role=role, kills=s["kills"], morts=s["deaths"], assists=s["assists"],
            cs=s["totalMinionsKilled"] + s["neutralMinionsKilled"], or_=s["goldEarned"],
            degats=s["totalDamageDealtToChampions"], vision=s["visionScore"], pinks=s["visionWardsBoughtInGame"],
            niveau=s["champLevel"], objets=[s[f"item{i}"] for i in range(7) if s.get(f"item{i}")],
            moi=p["participantId"] == mien,
        ))
    return joueurs


def _images(chrono: dict) -> list[dict]:
    return [
        {
            "t": image["timestamp"] / 1000,
            "positions": {int(i): [f["position"]["x"], f["position"]["y"]] for i, f in image["participantFrames"].items()
                          if f.get("position")},
            "or": {int(i): f["totalGold"] for i, f in image["participantFrames"].items()},
            "poche": {int(i): f["currentGold"] for i, f in image["participantFrames"].items()},
        }
        for image in chrono["frames"]
    ]


def position(images: list[dict], joueur: int, t: float) -> tuple[float, float] | None:
    """Où était un joueur à l'instant t : interpolé entre les deux relevés qui l'encadrent."""
    avant = max((i for i in images if i["t"] <= t and joueur in i["positions"]), key=lambda i: i["t"], default=None)
    apres = min((i for i in images if i["t"] > t and joueur in i["positions"]), key=lambda i: i["t"], default=None)
    if avant is None or apres is None:
        connu = avant or apres
        return tuple(connu["positions"][joueur]) if connu else None
    part = (t - avant["t"]) / (apres["t"] - avant["t"])
    (x0, y0), (x1, y1) = avant["positions"][joueur], apres["positions"][joueur]
    return x0 + (x1 - x0) * part, y0 + (y1 - y0) * part


def lieu(x: float, y: float, equipe: int) -> str:
    """Un point de la carte, dit du point de vue d'un joueur de `equipe`."""
    if dist((x, y), DRAKE) < 1500:
        return "au drake"
    if dist((x, y), BARON) < 1500:
        return "au Baron"
    chez_bleu = x + y < 14000
    chez_rouge = x + y > 16000
    chez_moi = chez_bleu if equipe == 100 else chez_rouge
    chez_eux = chez_rouge if equipe == 100 else chez_bleu
    cote = " de ton côté" if chez_moi else " de leur côté" if chez_eux else ""
    if (x < 3800 and y < 3800) or (x > 11200 and y > 11200):
        return "dans ta base" if chez_moi else "dans leur base"
    if y < 2800 or x > 12200:
        return "en botlane" + cote
    if x < 2800 or y > 12200:
        return "en toplane" + cote
    if abs(x - y) < 1500:
        return "en midlane" + cote
    if not chez_moi and not chez_eux:
        return "dans la rivière"
    return "dans ta jungle" if chez_moi else "dans leur jungle"


def series_de_kills(heures: list[float], combien: int = 3) -> list[tuple[float, int]]:
    """Les plus belles séries de kills : (heure du premier, nombre), kills à moins de 12 secondes d'écart."""
    series: list[tuple[float, int]] = []
    for i, t in enumerate(heures):
        if i == 0 or heures[i - 1] < t - 12:
            series.append((t, len([u for u in heures if t <= u < t + 12])))
    retenues = sorted((s for s in series if s[1] >= 2), key=lambda s: -s[1])[:combien]
    return sorted(retenues)


def _liste(noms: list[str]) -> str:
    return noms[0] if len(noms) == 1 else f"{', '.join(noms[:-1])} et {noms[-1]}" if noms else ""


def _mort(ev: dict, moi: Participant, joueurs: dict[int, Participant], images: list[dict], c: Reglages) -> tuple[Moment, str]:
    """Le moment et sa catégorie : inferiorite, lane, gank, isole, riche, objectif ou combat."""
    t, x, y = ev["timestamp"] / 1000, ev["position"]["x"], ev["position"]["y"]
    tueurs = [joueurs[i] for i in dict.fromkeys([ev["killerId"], *ev["assistingParticipantIds"]]) if i in joueurs]
    allies = sum(
        1 for j in joueurs.values()
        if j.equipe == moi.equipe and not j.moi and (p := position(images, j.id, t)) and dist(p, (x, y)) < A_PORTEE
    )
    releve = max((i for i in images if i["t"] <= t), key=lambda i: i["t"], default=images[0])
    poche = releve["poche"].get(moi.id, 0)
    ou = lieu(x, y, moi.equipe)
    jungler = next((j for j in tueurs if j.role == "jungle"), None)

    analyse = f"Tué par {_liste([j.champion for j in tueurs])}." if tueurs else "Exécuté par une tour ou des sbires."
    analyse += f" {len(tueurs)} contre {allies + 1}." if tueurs else ""
    if poche >= c.seuils.or_recall:
        analyse += f" {poche} gold en poche."

    en_lane = t <= c.saison["sbires"]["fin_de_lane"]
    if len(tueurs) >= allies + 3:
        categorie = "inferiorite"
        conseil = "Combat perdu d'avance : compte les présents avant d'avancer, et recule s'il manque deux alliés."
    elif en_lane and ou.startswith(("en botlane", "en toplane", "en midlane")):
        if jungler:
            categorie = "gank"
            avant = position(images, jungler.id, max(0.0, t - 45))
            analyse += f" {jungler.champion} était {lieu(*avant, moi.equipe)} 45 secondes avant." if avant else ""
            conseil = "Gank subi : vague de ton côté tant que leur jungler n'a pas été vu, et ward rivière avant d'avancer."
        elif len(tueurs) > allies + 1:
            categorie = "lane"
            conseil = "À un contre deux, on ne trade pas : recule sous ta tour tant que ton support n'est pas revenu."
        elif "de leur côté" in ou:
            categorie = "lane"
            conseil = "Trop avancé pour un combat à égalité : garde la vague de ton côté quand tu n'as ni l'avantage ni la vision."
        else:
            categorie = "lane"
            conseil = "Trade perdu : avant de t'engager, compare niveaux, sbires et sorts. Deux avantages sur trois, sinon on farme."
    elif allies == 0 and not en_lane and "base" not in ou:
        categorie = "isole"
        conseil = "Seul loin de ton équipe après la phase de lane : pas de side sans vision ni allié à portée."
    elif len(tueurs) >= allies + 2:
        categorie = "inferiorite"
        conseil = f"À {allies + 1} contre {len(tueurs)}, le combat part perdant : recule vers ta tour au lieu de l'accepter."
    elif poche >= c.seuils.or_recall:
        categorie = "riche"
        conseil = "Cet or devait être dépensé avant : back dès qu'il termine un objet, puis reviens te battre."
    elif "leur jungle" in ou or "leur base" in ou:
        categorie = "terrain"
        conseil = "Chez eux sans vision, ce sont eux qui choisissent le combat : n'y entre qu'avec ton équipe devant toi."
    elif ou in ("au drake", "au Baron", "dans la rivière"):
        categorie = "objectif"
        conseil = "Combat d'objectif perdu : arrive avec ton équipe, pas avant, et reste hors de portée tant que l'engage n'est pas parti."
    else:
        categorie = "combat"
        conseil = "En combat, reste derrière ta frontline et tape la cible la plus proche : tu es mort avant de faire tes dégâts."
    return Moment(t, "mort", f"Mort {ou}", analyse, conseil, x, y, [j.cle for j in tueurs]), categorie


def _presence(objectifs: list[dict], moi: Participant, images: list[dict]) -> tuple[int, int]:
    """(objectifs où j'étais sur place, objectifs majeurs joués) : drakes et Barons des deux équipes."""
    majeurs = [o for o in objectifs if o["nom"] in ("Drake", "Baron")]
    presents = sum(
        1 for o in majeurs if (p := position(images, moi.id, o["t"])) and dist(p, (o["x"], o["y"])) < PRESENT
    )
    return presents, len(majeurs)


def analyser(partie: dict, chrono: dict, puuid: str, c: Reglages) -> Bilan:
    joueurs = _participants(partie, puuid)
    par_id = {j.id: j for j in joueurs}
    moi = next((j for j in joueurs if j.moi), joueurs[0])
    adversaire = next((j for j in joueurs if j.equipe != moi.equipe and j.role == "adc"), None)
    images = _images(chrono)
    evenements = [ev for image in chrono["frames"] for ev in image["events"]]
    duree = partie["gameDuration"]
    minutes = max(duree / 60, 1)

    kills = [
        {"t": ev["timestamp"] / 1000, "x": ev["position"]["x"], "y": ev["position"]["y"],
         "tueur": ev["killerId"], "victime": ev["victimId"]}
        for ev in evenements if ev["type"] == "CHAMPION_KILL"
    ]
    objectifs = [
        {"t": ev["timestamp"] / 1000, "x": ev["position"]["x"], "y": ev["position"]["y"],
         "nom": MONSTRES.get(ev["monsterType"], ev["monsterType"]),
         "equipe": par_id[ev["killerId"]].equipe if ev["killerId"] in par_id else 0}
        for ev in evenements if ev["type"] == "ELITE_MONSTER_KILL"
    ]

    # --- Moments clés
    moments: list[Moment] = []
    categories: list[str] = []
    for ev in evenements:
        if ev["type"] == "CHAMPION_KILL" and ev["victimId"] == moi.id:
            moment, categorie = _mort(ev, moi, par_id, images, c)
            moments.append(moment)
            categories.append(categorie)
    miens = sorted(k["t"] for k in kills if k["tueur"] == moi.id)
    for t, nombre in series_de_kills(miens):
        if nombre:
            k = next(k for k in kills if k["t"] == t)
            moments.append(Moment(
                t, "exploit", f"{nombre} kills d'affilée {lieu(k['x'], k['y'], moi.equipe)}",
                "Bon combat : tu es resté en vie assez longtemps pour faire tes dégâts.",
                "Retiens le placement de ce combat, c'est celui à refaire.", k["x"], k["y"],
                [par_id[v["victime"]].cle for v in kills if v["tueur"] == moi.id and t <= v["t"] < t + 12],
            ))
    for o in objectifs:
        # On ne revient que sur ce qui pose question : un objectif majeur joué sans toi.
        ou = position(images, moi.id, o["t"])
        if o["nom"] not in ("Drake", "Baron") or o["equipe"] == 0 or ou is None or dist(ou, (o["x"], o["y"])) < PRESENT:
            continue
        if any(m.genre == "mort" and 0 <= o["t"] - m.t <= 45 for m in moments):
            continue  # tu venais de mourir : c'est la mort qu'il faut revoir, pas l'objectif
        if o["nom"] == "Drake" and o["t"] < c.saison["sbires"]["fin_de_lane"] and o["equipe"] != moi.equipe:
            continue  # un drake cédé pendant la lane est souvent le bon choix
        endroit = f"Tu étais {lieu(*ou, moi.equipe)}."
        if o["equipe"] == moi.equipe:
            titre, analyse = f"{o['nom']} pris sans toi", f"Ton équipe l'a fait à quatre. {endroit}"
            conseil = "Sois sur place une minute avant : vague poussée, puis décale avec ton support."
        else:
            titre, analyse = f"{o['nom']} cédé", f"Ils l'ont pris pendant que tu étais ailleurs. {endroit}"
            conseil = "Un objectif cédé doit rapporter autre chose : une tour, des plaques, l'objectif d'en face. Sinon, il fallait y être."
        moments.append(Moment(o["t"], "objectif", titre, analyse, conseil, o["x"], o["y"]))
    moments.sort(key=lambda m: m.t)

    # --- Chiffres
    equipe = [j for j in joueurs if j.equipe == moi.equipe]
    kills_equipe = sum(j.kills for j in equipe) or 1
    presents, majeurs = _presence(objectifs, moi, images)
    a_14 = min(images, key=lambda i: abs(i["t"] - c.saison["sbires"]["fin_de_lane"]))
    ecart_or = a_14["or"].get(moi.id, 0) - a_14["or"].get(adversaire.id, 0) if adversaire else 0
    chiffres = {
        "cs_par_minute": moi.cs / minutes,
        "part_degats": moi.degats / (sum(j.degats for j in equipe) or 1),
        "participation": (moi.kills + moi.assists) / kills_equipe,
        "presence": presents / majeurs if majeurs else 1.0,
        "presents": presents, "majeurs": majeurs,
        "vision_par_minute": moi.vision / minutes,
        "ecart_or_14": ecart_or,
    }

    # --- Leçons, de la plus coûteuse à la moins coûteuse
    lecons: list[Lecon] = []
    objectif_cs = c.seuils.cs_par_minute
    if chiffres["cs_par_minute"] < objectif_cs:
        manque = round((objectif_cs - chiffres["cs_par_minute"]) * minutes * 20, -2)
        compare = f" {adversaire.champion} en a pris {adversaire.cs}." if adversaire and adversaire.cs > moi.cs else ""
        lecons.append(Lecon(
            "Farm", f"{chiffres['cs_par_minute']:.1f} sbires par minute, pour un objectif de {objectif_cs:g}.{compare}".replace(".", ",", 1),
            f"Environ {int(manque)} gold laissés sur la carte. Entre deux objectifs, il y a toujours une vague à prendre.",
            manque / 300,
        ))
    for categorie, titre, constat, conseil, poids in (
        ("isole", "Morts loin de l'équipe", "seul, sans allié à portée",
         "Après la phase de lane, jamais seul en side sans vision : colle ton support ou ton jungler.", 5),
        ("inferiorite", "Combats perdus d'avance", "en nette infériorité numérique",
         "Compte les présents avant chaque combat. S'il manque deux alliés, on recule et on cède.", 5),
        ("riche", "Recalls trop tardifs", f"avec plus de {c.seuils.or_recall} gold en poche",
         "Back dès que ton or termine un objet : se battre avec l'objet vaut mieux que mourir avec l'or.", 4),
        ("lane", "Morts en lane", "en phase de lane, trop avancé ou à un contre deux",
         "La vague décide : de ton côté quand tu es en retard, sans vision ou sans support. On trade avec deux avantages.", 4),
        ("terrain", "Morts chez l'adversaire", "dans leur jungle ou leur base",
         "On n'entre dans leur jungle qu'avec la vision et l'équipe devant soi. L'ADC entre en dernier.", 4),
        ("objectif", "Combats d'objectif", "autour d'un drake ou du Baron",
         "Arrive avec ton équipe, vague poussée, et reste hors de portée tant que l'engage n'est pas parti.", 4),
        ("gank", "Ganks subis", "sur un gank en phase de lane",
         "Vague de ton côté tant que leur jungler n'est pas vu, et ward rivière avant de dépasser le milieu.", 4),
        ("combat", "Placement en combat", "en plein combat d'équipe",
         "Derrière ta frontline, la cible la plus proche d'abord. Mort, tu ne fais plus aucun dégât.", 3),
    ):
        n = categories.count(categorie)
        if n >= 2 or (n == 1 and moi.morts <= 3):
            lecons.append(Lecon(titre, f"{n} de tes {moi.morts} morts : {constat}.", conseil, poids * n))
    if adversaire and ecart_or <= -600:
        lecons.append(Lecon(
            "Phase de lane", f"{-ecart_or} gold de retard sur {adversaire.champion} à 14 minutes.",
            "La lane se gagne aux vagues et aux recalls : crash, back sur objet, et pas de trade en retard d'un composant.",
            -ecart_or / 250,
        ))
    if chiffres["vision_par_minute"] < 0.8 or moi.pinks == 0:
        lecons.append(Lecon(
            "Vision", f"Score de vision {moi.vision} en {round(minutes)} minutes, {moi.pinks} pink achetée{'s' if moi.pinks > 1 else ''}.",
            "Trinket dès qu'il est disponible, et une pink à chaque back tant qu'il reste une place.",
            4 if moi.pinks == 0 else 2,
        ))
    if chiffres["part_degats"] < 0.22:
        lecons.append(Lecon(
            "Dégâts en combat", f"{chiffres['part_degats']:.0%} des dégâts de ton équipe.",
            "Un ADC fait ses dégâts en restant en vie et à portée : tape ce qui est devant toi, ne cherche pas leur carry.",
            (0.25 - chiffres["part_degats"]) * 60,
        ))
    if majeurs >= 3 and chiffres["presence"] < 0.5:
        lecons.append(Lecon(
            "Présence aux objectifs", f"Sur place pour {presents} drakes et Barons sur {majeurs}.",
            "Sois là une minute avant : vague poussée, puis décale avec ton support.",
            (1 - chiffres["presence"]) * 6,
        ))
    lecons.sort(key=lambda lecon: -lecon.poids)

    points_forts = []
    if chiffres["cs_par_minute"] >= objectif_cs:
        points_forts.append(f"Farm solide : {chiffres['cs_par_minute']:.1f} sbires par minute.".replace(".", ",", 1))
    if moi.morts <= 3:
        points_forts.append(f"{moi.morts} mort{'s' if moi.morts > 1 else ''} seulement.")
    if chiffres["part_degats"] >= 0.28:
        points_forts.append(f"{chiffres['part_degats']:.0%} des dégâts de ton équipe.")
    if adversaire and ecart_or >= 600:
        points_forts.append(f"Lane gagnée : {ecart_or} gold d'avance sur {adversaire.champion} à 14 minutes.")
    if majeurs >= 3 and chiffres["presence"] >= 0.75:
        points_forts.append(f"Présent à {presents} objectifs majeurs sur {majeurs}.")

    victoire = next((t.get("win") == "Win" for t in partie["teams"] if t["teamId"] == moi.equipe), False)
    return Bilan(
        identifiant=partie["gameId"], file=FILES.get(partie.get("queueId", -1), "Partie"),
        date=partie.get("gameCreationDate", "")[:10], duree=duree, victoire=victoire, joueurs=joueurs, moi=moi,
        adversaire=adversaire, moments=moments, lecons=lecons[:4], points_forts=points_forts[:3], images=images,
        kills=kills, objectifs=objectifs, chiffres=chiffres,
    )
