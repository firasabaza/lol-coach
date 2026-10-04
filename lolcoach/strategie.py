"""Règles de coaching avancées : matchup, composition, build, pics de puissance, macro.

Elles complètent regles.py (les fondamentaux). Les principes et leurs sources sont dans
docs/CONNAISSANCES.md ; ce qui dépend des champions passe par compo.py.
"""

from __future__ import annotations

from collections.abc import Iterator

from .compo import (
    PLONGEURS, POKE, adaptations, bottes, chemin, classe, est, fiche, lire_compo, nom_objet, noms, notes, objets_finis,
    reste_a_payer,
)
from .datadragon import objets, runes
from .etat import PRIX_OBJET_FINI, ROLES_BOT, Etat
from .rapport import NET, avance, avance_lane, ennemis_morts, forme, puissance, score
from .reglages import Reglages
from .regles import INFO, TEMPO, URGENT, Conseil, Regle, duree, or_en_poche
from .suivi import Suivi, lire_structure

TRINKET_JAUNE = 3340
MAGES = {"MAGE", "BURST", "BATTLEMAGE"} | POKE


def _compte(n: int, mot: str) -> str:
    return f"{n} {mot}{'s' if n > 1 else ''}"


def plan_de_lane(e: Etat, s: Suivi, c: Reglages) -> Iterator[Conseil]:
    """Deux phrases sur le matchup, juste après l'annonce des champions."""
    if not 8 <= e.t < 70:
        return
    adc, sup, allie = e.ennemi("BOTTOM"), e.ennemi("UTILITY"), e.allie("UTILITY")
    points: list[str] = []
    if sup:
        if est(sup, "accroches"):
            points.append(f"{sup.champion} attrape de loin : reste derrière tes sbires, jamais dans l'axe.")
        elif est(sup, "engages"):
            points.append(f"{sup.champion} engage au contact : garde la vague de ton côté, ses niveaux 2, 3 et 6 tuent.")
        elif classe(sup, {"ENCHANTER"}):
            points.append(f"{sup.champion} gagne les trades longs : frappe quand son sort est parti, puis recule.")
        elif classe(sup, MAGES):
            points.append(f"{sup.champion} harcèle de loin : esquive d'abord, farme ensuite, pas aligné avec tes sbires.")
    if adc and fiche(adc) and fiche(e.moi):
        ecart = fiche(e.moi)["portee"] - fiche(adc)["portee"]
        if ecart >= 50:
            points.append(f"Tu as {ecart} de portée de plus que {adc.champion} : touche-le chaque fois qu'il prend un sbire.")
        elif ecart <= -50:
            points.append(f"{adc.champion} a {-ecart} de portée de plus que toi : pas de trade à l'auto, joue tes sorts.")
    if est(e.moi, "scaling"):
        points.append("Ton champion gagne avec le temps : la lane se joue pour le farm, pas pour le kill.")
    elif est(e.moi, "dominants"):
        points.append("Ton champion doit gagner la lane : prends la priorité dès le niveau 1.")
    if allie and (est(allie, "engages") or est(allie, "accroches")):
        points.append(f"{allie.champion} engage : suis à son premier contrôle.")
    elif allie and classe(allie, {"ENCHANTER"}):
        points.append(f"{allie.champion} te protège : c'est toi qui lances les trades.")
    if points:
        yield Conseil("plan-de-lane", INFO, "", " ".join(points[:2]))


def jungler_precoce(e: Etat, s: Suivi, c: Reglages) -> Iterator[Conseil]:
    jungler = e.jungler_ennemi
    if jungler and est(jungler, "ganks_precoces") and 95 <= e.t < 115:
        yield Conseil(
            "jungler-precoce", TEMPO, "",
            f"{jungler.champion} gank fort dès son premier passage : garde ta ward pour la rivière à 2 minutes.",
        )


def build(e: Etat, s: Suivi, c: Reglages) -> Iterator[Conseil]:
    """Le build type du champion, puis ce que la compo adverse impose."""
    if 25 <= e.t < 100 and (etapes := chemin(e.moi)):
        yield Conseil(
            "build-type", INFO, "",
            f"Build type sur {e.moi.champion} : {', puis '.join(nom_objet(i) for i in etapes)}.",
        )
    if not 45 <= e.t < 130:
        return
    compo = lire_compo(e)
    if not compo.ad and not compo.ap:
        return  # champions inconnus des données : rien à dire
    fait = f"En face : {_compte(len(compo.ad), 'physique')}, {_compte(len(compo.ap), 'magique')}"
    if compo.tanks:
        fait += f", {_compte(len(compo.tanks), 'tank')}"
    prevus = [f"{nom_objet(objet)} ({raison})" for objet, raison in adaptations(e)[:2]]
    if (chaussures := bottes(e)) is not None:
        prevus.append(f"{nom_objet(chaussures[0])} ({chaussures[1]})")
    action = f"À prévoir : {' ; '.join(prevus)}." if prevus else "Rien d'imposé : suis ton build."
    yield Conseil("build-adaptation", INFO, fait + ".", action)


def _prochain_objet(e: Etat) -> int | None:
    """L'objet à viser maintenant : la suite du chemin type, puis ce que la compo impose."""
    for objet in chemin(e.moi):
        if not e.moi.possede(objet):
            return objet
    return next((objet for objet, _ in adaptations(e)), None)


def objet_finissable(e: Etat, s: Suivi, c: Reglages) -> Iterator[Conseil]:
    """Le meilleur moment pour back : quand l'or en poche termine un objet."""
    if e.moi.mort or e.t - s.reapparu_a < 20 or (s.nb_achats and e.t - s.dernier_achat < 20):
        return
    if ennemis_morts(e) >= 3:
        return  # la carte est libre : on prend un objectif, l'achat attendra
    cible = _prochain_objet(e)
    if cible is None or objets().get(cible, {}).get("prix", 0) < PRIX_OBJET_FINI:
        return
    reste = reste_a_payer(cible, [o.id for o in e.moi.objets for _ in range(o.nombre)])
    poche = or_en_poche(e)
    if 0 < reste <= poche:
        action = (
            "Crash ta vague et back : c'est ton pic de puissance."
            if s.en_lane(e)
            else "Reset dès que ta vague est poussée, avant le prochain objectif."
        )
        yield Conseil(
            f"finir-{cible}", TEMPO, f"{int(poche // 50 * 50)} gold : {nom_objet(cible)} finissable.", action,
            intention="back",
        )


def pics(e: Etat, s: Suivi, c: Reglages) -> Iterator[Conseil]:
    finis = objets_finis(e.moi)
    if finis == 1:
        yield Conseil(
            "pic-1", TEMPO, "Premier objet terminé.",
            "Pic de puissance : cherche un trade ou un objectif dans les deux minutes.", intention="agressif",
        )
    elif finis == 2:
        suite = adaptations(e)
        ensuite = f" Ensuite : {nom_objet(suite[0][0])}, {suite[0][1]}." if suite else ""
        yield Conseil(
            "pic-2", TEMPO, "Deux objets terminés.",
            "Tu deviens la menace principale : groupe et joue les objectifs." + ensuite,
        )
    elif finis == 3:
        yield Conseil(
            "pic-3", INFO, "Trois objets terminés.",
            "Tu es la plus grosse menace de la partie : force les objectifs avec ton équipe, c'est toi qui gagnes les combats."
            if forme(e) == "domine"
            else "Un combat bien joué gagne la partie, une mort la perd : reste derrière ta frontline.",
        )

    adc = e.ennemi("BOTTOM")
    if adc and s.en_lane(e) and (siens := objets_finis(adc)) > finis and siens in (1, 2) and avance(e, adc) < 0:
        rang = "premier" if siens == 1 else "deuxième"
        yield Conseil(
            f"adc-pic-{siens}", TEMPO, f"{adc.champion} a fini son {rang} objet avant toi.",
            "Les trades sont perdants jusqu'à ton prochain back : farm à distance.", intention="prudent",
        )


def menaces(e: Etat, s: Suivi, c: Reglages) -> Iterator[Conseil]:
    """Les ennemis nourris, lus contre ta propre force : une menace, ou une prime à prendre."""
    compo = lire_compo(e)
    for j in e.ennemis:
        if j.kills < 4 or j.kills - j.morts < 3:
            continue
        marge = avance(e, j)
        if marge >= NET:
            yield Conseil(
                f"menace-{j.nom}", INFO,
                f"{j.champion} est à {score(j)}, mais tu as {round(marge, -2):.0f} gold de puissance de plus.",
                "Tu gagnes le duel si tu gardes ta distance : sa prime est pour toi.", intention="agressif",
            )
        elif j in compo.plongeurs:
            yield Conseil(
                f"menace-{j.nom}", URGENT, f"{j.champion} est à {score(j)}.",
                "Un combo suffit pour te tuer : reste à portée de ton support, jamais seul en side.",
                intention="prudent",
            )
        elif j in compo.poke or classe(j, MAGES):
            yield Conseil(
                f"menace-{j.nom}", TEMPO, f"{j.champion} est à {score(j)}.",
                "Ses sorts te sortent du combat : reste hors de portée et laisse ta frontline l'approcher.",
                intention="prudent",
            )
        elif j in compo.tanks:
            yield Conseil(
                f"menace-{j.nom}", TEMPO, f"{j.champion} est à {score(j)}.",
                "Ne reste pas à sa portée : recule en tapant, tu fais plus de dégâts que lui sur la durée.",
            )
        else:
            yield Conseil(
                f"menace-{j.nom}", TEMPO, f"{j.champion} est à {score(j)}.",
                "Pas de duel à l'auto : attends ton équipe pour le prendre, sa prime vous relance.",
                intention="prudent",
            )


def etat_du_joueur(e: Etat, s: Suivi, c: Reglages) -> Iterator[Conseil]:
    """Devant ou derrière : ce que ça change à ta façon de jouer."""
    if e.t < 300:
        return
    etat = forme(e)
    if etat == "domine":
        yield Conseil(
            "nourri", TEMPO, f"Tu es à {score(e.moi)} : la partie se joue autour de toi.",
            "Chaque objectif se prend avec toi. Force les combats avec ton équipe à portée : c'est toi qui les gagnes.",
            repeter_apres=480, intention="agressif",
        )
    elif etat == "retard":
        yield Conseil(
            "en-retard", TEMPO, f"Tu es en retard ({score(e.moi)}).",
            "Prends les vagues sûres, laisse ton équipe engager, et vise deux objets sans mourir.",
            repeter_apres=480, intention="prudent",
        )
    if e.moi.morts >= 2 and e.t < 600 and e.moi.kills < e.moi.morts and etat != "domine":
        yield Conseil(
            "morts-precoces", TEMPO, "Deux morts avant dix minutes.",
            "Nouveau plan : farm sous tour, zéro trade, et tes deux objets sans mourir.", intention="prudent",
        )


def ultis(e: Etat, s: Suivi, c: Reglages) -> Iterator[Conseil]:
    """Les ultis qui changent ta lane, d'où qu'ils viennent : engage, arrivée en bot, dégâts à distance."""
    for j in (e.ennemi("UTILITY"), e.jungler_ennemi):
        if j and j.niveau >= 6 and est(j, "ultis_engage"):
            yield Conseil(
                f"ulti-{j.nom}", TEMPO, f"{j.champion} est niveau 6.",
                "Son ulti t'attrape de loin : garde ton Flash pour l'esquiver, pas pour attaquer.",
            )
    if not s.en_lane(e):
        return
    for j in e.ennemis:
        if j.niveau < 6 or j.role in ROLES_BOT:
            continue
        if est(j, "ultis_arrivee"):
            yield Conseil(
                f"ulti-{j.nom}", TEMPO, f"{j.champion} est niveau 6.",
                "Son ulti l'amène en bot en quelques secondes : s'il disparaît de sa lane, pas de plongée.",
            )
        elif est(j, "ultis_degats"):
            yield Conseil(
                f"ulti-{j.nom}", INFO, f"{j.champion} est niveau 6.",
                "Son ulti touche de n'importe où : ne reste pas en lane avec peu de PV.",
            )


def etat_de_partie(e: Etat, s: Suivi, c: Reglages) -> Iterator[Conseil]:
    """Toutes les cinq minutes : qui mène, où tu en es, qui craindre et qui viser."""
    for minute in (10, 15, 20, 25, 30):
        if not minute * 60 + 35 <= e.t < minute * 60 + 65:
            continue
        nous = sum(j.kills for j in e.allies)
        eux = sum(j.kills for j in e.ennemis)
        tours = [lire_structure(ev.cible) for ev in e.evenements if ev.nom == "TurretKilled"]
        prises = sum(1 for t in tours if t and t[0] != e.moi.equipe)
        perdues = sum(1 for t in tours if t and t[0] == e.moi.equipe)
        drakes = s.drakes[e.moi.equipe] - sum(n for equipe, n in s.drakes.items() if equipe != e.moi.equipe)
        marge = (nous - eux) + 2 * (prises - perdues) + 2 * drakes
        etat = forme(e)
        fait = f"{minute} minutes : {nous} kills à {eux}, tours {prises} à {perdues}."
        if marge >= 5 and etat == "domine":
            action = "Vous menez et tu es devant : force les objectifs, chaque kill doit donner une tour."
        elif marge >= 5:
            action = "Vous menez. Chaque kill doit donner une tour ou un objectif dans les trente secondes."
        elif marge <= -5 and etat == "domine":
            action = "Vous êtes derrière, mais tu es le plus fort des tiens : c'est autour de toi que ça se joue. Combats à côté de tes alliés."
        elif marge <= -5:
            action = "Vous êtes derrière. Ne conteste que sous vision, farme ce qui vient à toi et attends leur erreur."
        else:
            action = "Partie serrée : le prochain objectif décide. Sois sur place une minute avant."
        yield Conseil(f"etat-{minute}", INFO, fait, action)

        # Qui craindre, qui viser : toute l'équipe d'en face, pas seulement leur ADC.
        fort = max(e.ennemis, key=lambda j: puissance(e, j), default=None)
        faible = min(e.ennemis, key=lambda j: puissance(e, j), default=None)
        lecture = []
        if fort and avance(e, fort) <= -NET:
            lecture.append(f"Leur plus fort : {fort.champion}, {score(fort)}. Ne te bats pas à sa portée sans ton équipe.")
        if faible and faible is not fort and avance(e, faible) >= NET:
            lecture.append(f"Leur plus faible : {faible.champion}, {score(faible)}. C'est ta cible quand il est à portée.")
        if lecture:
            yield Conseil(f"ennemis-{minute}", INFO, "", " ".join(lecture))

        adc = e.ennemi("BOTTOM")
        if adc and minute <= 20 and abs(ecart := adc.cs - e.moi.cs) >= 20:
            if ecart > 0:
                yield Conseil(
                    f"farm-ecart-{minute}", INFO,
                    f"{adc.champion} a environ {ecart} sbires d'avance, soit {ecart * 20} gold.",
                    "Chaque vague compte : ne quitte la lane que pour un objectif.",
                )
            else:
                yield Conseil(
                    f"farm-ecart-{minute}", INFO, f"Tu as environ {-ecart} sbires d'avance sur {adc.champion}.",
                    "C'est un demi-objet d'avance : transforme-le en plaques et en tours.",
                )


def nombres(e: Etat, s: Suivi, c: Reglages) -> Iterator[Conseil]:
    allies_morts = sum(j.mort for j in e.allies if j.nom != e.moi.nom)
    ennemis_morts = sum(j.mort for j in e.ennemis)
    if e.t > 300 and not e.moi.mort and allies_morts >= 2 and allies_morts - ennemis_morts >= 2:
        yield Conseil(
            "inferiorite", URGENT, f"{allies_morts} alliés morts.",
            "Ne défends pas seul : recule et nettoie les vagues sous ta tour.", repeter_apres=60, intention="danger",
        )

    jungler = e.allie("JUNGLE")
    reste = s.prochain_drake - e.t
    if jungler and jungler.mort and -10 < reste <= 45 and jungler.reapparition > max(reste, 0) + 5:
        yield Conseil(
            f"sans-jungler-{int(s.prochain_drake // 10)}", TEMPO, "Ton jungler est mort au moment du drake.",
            "Sans Smite, ne le conteste pas : prends la vision et une tour de l'autre côté.",
        )


def grands_objectifs(e: Etat, s: Suivi, c: Reglages) -> Iterator[Conseil]:
    """Baron, âme et Elder : ce que leur prise change pour les minutes qui suivent."""
    for ev in s.nouveaux:
        tueur = e.joueur(ev.tueur)
        if tueur is None:
            continue
        pour_nous = tueur.equipe == e.moi.equipe
        if ev.nom == "BaronKill" and pour_nous:
            yield Conseil(
                f"baron-pris-{ev.id}", TEMPO, "Baron pour vous.",
                "Back, achète, puis siège avec les sbires renforcés. Trois minutes : ne te fais pas attraper seul.",
            )
        elif ev.nom == "BaronKill":
            yield Conseil(
                f"baron-pris-{ev.id}", URGENT, "Baron pour eux.",
                "Nettoie les vagues sous tes tours, pas de combat dans leurs sbires. Tiens trois minutes.",
            )
        elif ev.nom == "DragonKill" and ev.type_drake == "Elder" and pour_nous:
            yield Conseil(
                f"elder-pris-{ev.id}", TEMPO, "Elder pour vous.",
                "Forcez la fin maintenant : toute cible basse en vie est exécutée.",
            )
        elif ev.nom == "DragonKill" and ev.type_drake == "Elder":
            yield Conseil(
                f"elder-pris-{ev.id}", URGENT, "Elder pour eux.",
                "Pas de combat pendant deux minutes trente : nettoie les vagues de loin.",
            )
        elif ev.nom == "DragonKill" and s.drakes[tueur.equipe] == c.saison["objectifs"]["drakes_pour_ame"]:
            if pour_nous:
                yield Conseil(
                    "ame-prise", TEMPO, "Âme du dragon pour vous.",
                    "L'Elder arrive dans six minutes : gardez la vision dessus, pas de combat inutile.",
                )
            else:
                yield Conseil(
                    "ame-prise", URGENT, "Ils ont l'âme du dragon.",
                    "Seuls l'Elder et le Baron vous relancent : vision dessus dès maintenant, combats à cinq uniquement.",
                )


def milieu_de_partie(e: Etat, s: Suivi, c: Reglages) -> Iterator[Conseil]:
    fin = c.saison["sbires"]["fin_de_lane"]
    compo = lire_compo(e)
    if fin + 20 <= e.t < fin + 50 and compo.plongeurs and forme(e) != "domine":
        yield Conseil(
            "milieu-plongeurs", TEMPO, "",
            f"Milieu de partie : {noms(compo.plongeurs)} {'cherchent' if len(compo.plongeurs) > 1 else 'cherche'} "
            "les cibles isolées. "
            "Jamais seul en side sans vision, reste avec ton support.", intention="prudent",
        )
    if e.moi.niveau >= 9 and e.moi.possede(TRINKET_JAUNE) and not s.en_lane(e):
        yield Conseil(
            "trinket-bleu", INFO, "Niveau 9 et toujours le trinket jaune.",
            f"Passe à l'{nom_objet(3363)} : tu éclaires un buisson sans t'en approcher.",
        )

    avant_baron = c.saison["objectifs"]["baron"] - 120
    if not avant_baron <= e.t < avant_baron + 30:
        return
    if len(compo.plongeurs) >= 2:
        plan = f"laisse {noms(compo.plongeurs)} plonger, recule, puis tue ce qui arrive sur toi. La cible la plus proche, pas leur carry."
    elif len(compo.ultis_engage) >= 2:
        plan = f"ne te mets pas dans l'axe de {noms(compo.ultis_engage)}. Ton Flash sert à esquiver leur engage."
    elif compo.poke:
        plan = f"{noms(compo.poke)} vous use de loin. N'attendez pas devant l'objectif : engagez vite ou cédez-le."
    elif len(compo.tanks) >= 2:
        plan = "leurs tanks tiennent longtemps. Tape le plus proche et reste hors de portée, les dégâts viennent avec le temps."
    else:
        plan = "derrière ta frontline, la cible la plus proche d'abord."
    yield Conseil("plan-de-combat", INFO, "", f"Plan de combat : {plan}")


def lecture_adverse(e: Etat, s: Suivi, c: Reglages) -> Iterator[Conseil]:
    """Ce que leur botlane a choisi : le sort clé du support et sa recharge, les runes, les sorts d'invocateur."""
    if not 60 <= e.t < 100:
        return
    table = notes()
    points: list[str] = []
    support = e.ennemi("UTILITY")
    lettres = {cle.lower(): lettre for cle, lettre in table.get("sorts_cles", {}).items()}
    sort = fiche(support).get("sorts", {}).get(lettres.get(support.cle.lower(), "")) if support else None
    if sort and sort["recharge"] >= 8:
        points.append(
            f"{sort['nom']} de {support.champion} : {sort['recharge']:g} secondes de recharge. "
            "Dès que ce sort est parti, tu as ce temps pour trader."
        )
    duo = [j for j in (e.ennemi("BOTTOM"), support) if j]
    for j in duo:
        if modele := table.get("runes", {}).get(str(j.rune)):
            points.append(modele.format(nom=j.champion, rune=runes().get(j.rune, "sa rune")))
            break
    for identifiant, modele in table.get("sorts_ennemis", {}).items():
        porteurs = [j for j in duo if any(porte.id == identifiant for porte in j.sorts)]
        if porteurs:
            points.append(modele.format(nom=noms(porteurs)))
            break
    if points:
        yield Conseil("lecture-adverse", INFO, "", " ".join(points[:2]))


def objets_adverses(e: Etat, s: Suivi, c: Reglages) -> Iterator[Conseil]:
    """Un ennemi vient d'acheter un objet qui change la façon de le combattre."""
    table = notes().get("objets_ennemis", {})
    if e.t < 300:
        return
    for j in e.ennemis:
        for objet in j.objets:
            if modele := table.get(str(objet.id)):
                fait, _, action = modele.format(nom=j.champion).partition(" | ")
                yield Conseil(f"objet-{j.nom}-{objet.id}", INFO, fait, action)


def tournants(e: Etat, s: Suivi, c: Reglages) -> Iterator[Conseil]:
    """Ace et inhibiteurs : les moments où la partie peut se finir ou se retourner."""
    for ev in s.nouveaux:
        if ev.nom == "Ace" and ev.equipe == e.moi.equipe:
            continue  # dit par la règle d'avantage numérique, qui choisit l'objectif
        elif ev.nom == "Ace":
            yield Conseil(
                f"ace-{ev.id}", URGENT, "Ace pour eux.",
                "À la réapparition, défendez à cinq sous vos tours : personne ne sort seul.", intention="danger",
            )
        elif ev.nom == "InhibKilled" and (tueur := e.joueur(ev.tueur)):
            if tueur.equipe == e.moi.equipe:
                yield Conseil(
                    f"inhibiteur-{ev.id}", TEMPO, "Inhibiteur détruit.",
                    "Les super-sbires poussent cette lane tout seuls : jouez l'objectif du côté opposé.",
                )
            else:
                yield Conseil(
                    f"inhibiteur-{ev.id}", URGENT, "Inhibiteur perdu.",
                    "Quelqu'un doit nettoyer les super-sbires. Pas de Baron ni de drake à quatre.",
                )
        elif ev.nom == "InhibRespawningSoon" and (structure := lire_structure(ev.cible)) and structure[0] != e.moi.equipe:
            yield Conseil(
                f"inhibiteur-retour-{ev.id}", TEMPO, "Leur inhibiteur revient dans 30 secondes.",
                "Dernière fenêtre pour forcer avec les super-sbires.",
            )


def condition_de_victoire(e: Etat, s: Suivi, c: Reglages) -> Iterator[Conseil]:
    """À 15 minutes : comment ton équipe gagne ses combats, d'après sa composition."""
    if not 900 <= e.t < 930:
        return
    allies = [j for j in e.allies if j.nom != e.moi.nom]
    engages = [j for j in allies if classe(j, {"VANGUARD"}) or est(j, "engages")]
    protecteurs = [j for j in allies if classe(j, {"ENCHANTER", "WARDEN"})]
    artilleurs = [j for j in allies if classe(j, POKE)]
    plongeurs = [j for j in allies if classe(j, PLONGEURS)]
    if engages:
        plan = f"votre combat part de {noms(engages)}. Reste à portée derrière, et tape dès que le contrôle est parti."
    elif len(protecteurs) >= 2:
        plan = f"{noms(protecteurs)} jouent pour toi : tu es la condition de victoire. Combats lents, autour de toi."
    elif len(artilleurs) >= 2:
        plan = f"{noms(artilleurs)} usent de loin : assiégez et harcelez avant l'objectif, n'engagez pas."
    elif len(plongeurs) >= 2:
        plan = f"{noms(plongeurs)} plongent sur leurs carrys : suis-les, les ennemis regardent ailleurs et tu tapes libre."
    else:
        return
    yield Conseil("condition-de-victoire", INFO, "", f"Votre plan de combat : {plan}")


def retard_de_niveau(e: Etat, s: Suivi, c: Reglages) -> Iterator[Conseil]:
    adc = e.ennemi("BOTTOM")
    if adc and s.en_lane(e) and adc.niveau >= e.moi.niveau + 2:
        yield Conseil(
            "niveaux-retard", URGENT, f"{adc.champion} a deux niveaux d'avance.",
            "Aucun trade : farm sous ta tour jusqu'à combler l'écart.",
        )


def rotations(e: Etat, s: Suivi, c: Reglages) -> Iterator[Conseil]:
    """Quand quitter sa lane, et pour quoi faire."""
    if e.moi.mort:
        return
    lane = s.en_lane(e)
    mid = e.ennemi("MIDDLE")
    if (mid and mid.mort and mid.reapparition >= 15 and e.t - s.morts_ennemies.get(mid.nom, e.t) <= 3
            and e.t > 240 and forme(e) != "retard" and ennemis_morts(e) < 3):
        yield Conseil(
            "rotation-mid", TEMPO, f"{mid.champion} est mort, {duree(mid.reapparition)}.",
            "Si ta vague est poussée, monte mid avec ton support : à trois, la tour ou les plaques tombent."
            if lane
            else "Pousse mid tout de suite : la tour est à prendre.",
            repeter_apres=150, intention="agressif",
        )

    canon = s.prochain_canon(e.t) - e.t
    if lane and e.t > 300 and avance_lane(e) >= NET and 5 <= canon <= 15:
        yield Conseil(
            "rotation-canon", INFO, f"Vague canon dans {duree(canon)}.",
            "Crash-la : tu gagnes vingt secondes pour une ward profonde avec ton support, ou pour les plaques.",
            repeter_apres=240, intention="agressif",
        )

    # Après chaque objectif pris : quoi faire jusqu'au suivant.
    o = c.saison["objectifs"]
    for ev in s.nouveaux:
        if lane or ev.nom not in ("DragonKill", "BaronKill", "HeraldKill"):
            continue
        suivants = [("Elder" if s.elder else "Drake", s.prochain_drake, "bot"), ("Baron", s.prochain_baron, "top")]
        if not s.herald_pris and e.t < o["herald"]:
            suivants.append(("Herald", float(o["herald"]), "top"))
        a_venir = [p for p in suivants if p[1] > e.t + 45]
        if a_venir:
            nom, quand, cote = min(a_venir, key=lambda p: p[1])
            yield Conseil(
                f"plan-{ev.id}", INFO, f"Prochain objectif : {nom} dans {duree(round((quand - e.t) / 10) * 10)}.",
                f"D'ici là, pousse mid, puis la side {cote} avec ton support. Reviens une minute avant.",
            )


REGLES: tuple[Regle, ...] = (
    plan_de_lane, lecture_adverse, jungler_precoce, build, objet_finissable, pics, menaces, etat_du_joueur, ultis,
    retard_de_niveau, objets_adverses, rotations, etat_de_partie, nombres, grands_objectifs, tournants,
    condition_de_victoire, milieu_de_partie,
)
