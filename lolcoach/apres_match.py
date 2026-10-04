"""La fenêtre d'après-match : récapitulatif illustré, points à améliorer, moments clés, revue de carte.

Les données viennent du client League (lcu.py), l'analyse de bilan.py, les images de Data Dragon.
La page est un fichier HTML autonome, ouvert dans une fenêtre sans barre d'adresse.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from html import escape as h
from pathlib import Path

from . import debrief
from .bilan import CARTE, Bilan, Participant, analyser
from .bilan_coach import depuis_enregistrement
from .datadragon import image, objets
from .enregistreur import relire
from .etat import depuis_json
from .lcu import ClientLol
from .reglages import RACINE, Reglages

NAVIGATEURS = (
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
)
ROLES = {"jungle": "Jungle", "adc": "ADC", "support": "Support", "solo": ""}
MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre")


# --- Lecture du client -----------------------------------------------------------------------------


def charger(client: ClientLol, identifiant: int | None = None, depuis: float = 0.0) -> tuple[dict, dict, str] | None:
    """(partie, chronologie, mon puuid) de la partie `identifiant`, ou de la dernière vraie partie.

    `depuis` (heure Unix) écarte les parties créées avant : sert à attendre celle qui vient de finir.
    """
    moi = client.lire("/lol-summoner/v1/current-summoner")
    if not moi:
        return None
    if identifiant is None:
        historique = client.lire("/lol-match-history/v1/products/lol/current-summoner/matches?begIndex=0&endIndex=10")
        jeux = (historique or {}).get("games", {}).get("games", [])
        recente = next(
            (j for j in jeux if j.get("gameDuration") and j.get("mapId") == 11 and j.get("gameCreation", 0) / 1000 >= depuis),
            None,
        )
        if recente is None:
            return None
        identifiant = recente["gameId"]
    partie = client.lire(f"/lol-match-history/v1/games/{identifiant}")
    chrono = client.lire(f"/lol-match-history/v1/game-timelines/{identifiant}")
    if not partie or not chrono or not chrono.get("frames") or not partie.get("gameDuration"):
        return None
    return partie, chrono, moi["puuid"]


def attendre(client: ClientLol, depuis: float, patience: float = 45.0) -> tuple[dict, dict, str] | None:
    """Attend que le client ait enregistré la partie qui vient de finir."""
    limite = time.monotonic() + patience
    while True:
        trouve = charger(client, depuis=depuis)
        if trouve or time.monotonic() >= limite:
            return trouve
        time.sleep(5)


# --- Rendu -------------------------------------------------------------------------------------------


def _temps(t: float) -> str:
    return f"{int(t) // 60}:{int(t) % 60:02d}"


def _nombre(n: float) -> str:
    return f"{round(n):,}".replace(",", "\u202f")


def _date(iso: str) -> str:
    try:
        annee, mois, jour = (int(x) for x in iso.split("-"))
        return f"{jour} {MOIS[mois - 1]} {annee}"
    except (ValueError, IndexError):
        return iso


class _Images:
    """Adresses des images, relatives au dossier où la page sera écrite."""

    def __init__(self, dossier: Path):
        self._dossier = dossier

    def __call__(self, genre: str, nom: object) -> str:
        fichier = image(genre, str(nom)) if nom else None
        return Path(os.path.relpath(fichier, self._dossier)).as_posix() if fichier else ""


def _portrait(j: Participant, img: _Images, classe: str = "portrait") -> str:
    return f'<img class="{classe}" src="{img("champion", j.cle)}" alt="{h(j.champion)}" title="{h(j.champion)}">'


def _objets(j: Participant, img: _Images) -> str:
    cases = []
    for identifiant in j.objets:
        nom = objets().get(identifiant, {}).get("nom", "")
        source = img("objet", identifiant)
        cases.append(f'<img src="{source}" alt="{h(nom)}" title="{h(nom)}">' if source else '<span class="vide"></span>')
    cases += ['<span class="vide"></span>'] * (7 - len(cases))
    return f'<div class="objets">{"".join(cases)}</div>'


def _tableau(b: Bilan, img: _Images) -> str:
    plafond = max(j.degats for j in b.joueurs)
    blocs = []
    for equipe in (b.moi.equipe, 300 - b.moi.equipe):
        lignes = []
        for j in (x for x in b.joueurs if x.equipe == equipe):
            role = f'<span class="role">{ROLES[j.role]}</span>' if ROLES[j.role] else ""
            lignes.append(
                f'<tr class="{"moi" if j.moi else ""}"><td class="qui">{_portrait(j, img)}<span>{h(j.champion)}{role}</span></td>'
                f'<td class="kda">{j.kills}<i>/</i>{j.morts}<i>/</i>{j.assists}</td><td>{j.cs}</td><td>{_nombre(j.or_)}</td>'
                + (f'<td class="degats"><span class="barre"><span style="width:{j.degats / plafond:.0%}"></span></span>'
                   f"{_nombre(j.degats)}</td>" if plafond else "") +
                f'<td>{j.vision}</td><td>{_objets(j, img)}</td></tr>'
            )
        titre = "Ton équipe" if equipe == b.moi.equipe else "Équipe adverse"
        if b.victoire is not None:
            titre += " · victoire" if (equipe == b.moi.equipe) == b.victoire else " · défaite"
        or_ = "Or" if b.source == "client" else "Or en objets"
        degats = "<th>Dégâts aux champions</th>" if plafond else ""
        colonnes = (20, 10, 8, 9, 21, 7, 25) if plafond else (26, 12, 10, 12, 9, 31)
        blocs.append(
            f'<table class="equipe {"alliee" if equipe == b.moi.equipe else "adverse"}"><caption>{titre}</caption>'
            f'<colgroup>{"".join(f"""<col style="width:{largeur}%">""" for largeur in colonnes)}</colgroup>'
            f"<thead><tr><th>Champion</th><th>K/D/A</th><th>Sbires</th><th>{or_}</th>{degats}<th>Vision</th><th>Objets</th></tr></thead>"
            f'<tbody>{"".join(lignes)}</tbody></table>'
        )
    return "".join(blocs)


def _moments(b: Bilan, img: _Images, carte: bool) -> str:
    par_cle = {j.cle: j for j in b.joueurs}
    signes = {"mort": ("✕", "Mort"), "exploit": ("★", "Bon moment"), "objectif": ("⚑", "Objectif")}
    articles = []
    for m in b.moments:
        signe, nom = signes[m.genre]
        acteurs = "".join(_portrait(par_cle[cle], img, "acteur") for cle in m.acteurs if cle in par_cle)
        articles.append(
            f'<article class="moment {m.genre}"><div class="quand"><span class="signe" aria-hidden="true">{signe}</span>'
            f'<time>{_temps(m.t)}</time><span class="genre">{nom}</span></div>'
            f'<div class="quoi"><h3>{h(m.titre)}</h3><div class="acteurs">{acteurs}</div><p>{h(m.analyse)}</p>'
            f'<p class="conseil">{h(m.conseil)}</p></div>'
            + (f'<button class="voir" data-t="{m.t:.0f}" data-x="{m.x:.0f}" data-y="{m.y:.0f}">Voir sur la carte</button>'
               if carte else "") + "</article>"
        )
    return "".join(articles) or '<p class="rien">Aucun moment à revoir : ni mort, ni objectif joué sans toi.</p>'


def _courbe(b: Bilan) -> str:
    """Or total minute par minute : toi et leur ADC."""
    if b.adversaire is None or len(b.images) < 3:
        return ""
    largeur, hauteur, gauche, droite, haut, bas = 1040, 270, 56, 170, 16, 30
    moi = [(i["t"], i["or"].get(b.moi.id, 0)) for i in b.images]
    lui = [(i["t"], i["or"].get(b.adversaire.id, 0)) for i in b.images]
    fin = moi[-1][0] or 1
    plafond = max(2500, -(-max(v for _, v in moi + lui) // 2500) * 2500)

    def x(t: float) -> float:
        return gauche + (largeur - gauche - droite) * t / fin

    def y(v: float) -> float:
        return haut + (hauteur - haut - bas) * (1 - v / plafond)

    svg = []
    for palier in range(0, int(plafond) + 1, 2500):
        svg.append(f'<line class="grille" x1="{gauche}" x2="{largeur - droite}" y1="{y(palier):.1f}" y2="{y(palier):.1f}"/>')
        svg.append(f'<text class="graduation" x="{gauche - 8}" y="{y(palier) + 4:.1f}" text-anchor="end">{_nombre(palier)}</text>')
    for t in range(0, int(fin) + 1, 300):
        svg.append(f'<text class="graduation" x="{x(t):.1f}" y="{hauteur - 8}" text-anchor="middle">{_temps(t)}</text>')
    for serie, points, nom in (("s2", lui, b.adversaire.champion), ("s1", moi, "Toi")):
        trace = " ".join(f"{x(t):.1f},{y(v):.1f}" for t, v in points)
        svg.append(f'<polyline class="ligne {serie}" points="{trace}"/>')
        svg.append(f'<circle class="bout {serie}" cx="{x(points[-1][0]):.1f}" cy="{y(points[-1][1]):.1f}" r="4.5"/>')
        svg.append(f'<text class="etiquette" x="{x(points[-1][0]) + 10:.1f}" y="{y(points[-1][1]) + 4:.1f}">{h(nom)} · {_nombre(points[-1][1])}</text>')
    svg.append(f'<line class="repere" id="repere" y1="{haut}" y2="{hauteur - bas}" visibility="hidden"/>')
    lignes = "".join(f"<tr><td>{_temps(t)}</td><td>{_nombre(v)}</td><td>{_nombre(w)}</td></tr>" for (t, v), (_, w) in zip(moi, lui))
    donnees = json.dumps({"moi": moi, "lui": lui, "x0": gauche, "x1": largeur - droite, "fin": fin, "nom": b.adversaire.champion})
    estime = "" if b.source == "client" else " Pour l'adversaire, c'est une estimation d'après ses objets et son score."
    return f"""
<section id="or"><h2>Or total</h2>
<p class="note">Toi et {h(b.adversaire.champion)}, minute par minute. L'écart qui se creuse montre où la partie a tourné.{estime}</p>
<figure class="graphique">
  <div class="cle"><span><i class="trait s1"></i>Toi</span><span><i class="trait s2"></i>{h(b.adversaire.champion)}</span></div>
  <div class="cadre" id="cadre"><svg viewBox="0 0 {largeur} {hauteur}" width="{largeur}" height="{hauteur}" role="img" tabindex="0" id="courbe"
    aria-label="Or total de toi et de leur ADC au fil de la partie">{''.join(svg)}</svg>
    <div class="bulle" id="bulle" hidden></div></div>
  <details><summary>Voir les données</summary><table class="donnees"><thead><tr><th>Temps</th><th>Toi</th><th>{h(b.adversaire.champion)}</th></tr></thead><tbody>{lignes}</tbody></table></details>
</figure><script type="application/json" id="donnees-or">{donnees}</script></section>"""


def rendre(b: Bilan, c: Reglages, dossier: Path, coach: str = "") -> str:
    """La page complète. `coach` : HTML de ce que le coach a dit pendant la partie, s'il y était."""
    img = _Images(dossier)
    moi, k = b.moi, b.chiffres
    ecart = k["ecart_or_14"]
    valeurs = [(f"{k['cs_par_minute']:.1f}".replace(".", ","), "sbires par minute")]
    if "part_degats" in k:
        valeurs.append((f"{k['part_degats']:.0%}", "des dégâts de l'équipe"))
    else:
        valeurs.append((str(moi.vision), "de score de vision"))
    valeurs.append((f"{k['participation']:.0%}", "des kills joués"))
    valeurs.append((f"{'+' if ecart > 0 else ''}{_nombre(ecart)}", "gold d'écart à 14 min"))
    tuiles = "".join(
        f'<div class="tuile"><div class="valeur">{valeur}</div><div class="label">{label}</div></div>'
        for valeur, label in valeurs
    )
    a_carte = any(i["positions"] for i in b.images)
    if b.victoire is None:
        resultat, classe_resultat = "Entraînement", "neutre"
    else:
        resultat, classe_resultat = ("Victoire", "victoire") if b.victoire else ("Défaite", "defaite")
    lecons = "".join(
        f'<li><h3>{h(lecon.titre)}</h3><p class="constat">{h(lecon.constat)}</p><p>{h(lecon.conseil)}</p></li>'
        for lecon in b.lecons
    ) or "<li><h3>Rien de majeur</h3><p>Pas d'erreur qui se répète sur cette partie.</p></li>"
    forts = "".join(f"<li>{h(texte)}</li>" for texte in b.points_forts)
    forts = f'<ul class="forts" aria-label="Points forts">{forts}</ul>' if forts else ""

    pions = "".join(
        f'<div class="pion {"allie" if j.equipe == moi.equipe else "ennemi"}{" moi" if j.moi else ""}" data-id="{j.id}" '
        f'style="background-image:url({img("champion", j.cle)})" title="{h(j.champion)}"></div>'
        for j in sorted(b.joueurs, key=lambda j: j.moi)
    )
    carte = json.dumps({
        "duree": b.duree, "bords": CARTE, "moi": moi.equipe,
        "images": [{"t": i["t"], "p": i["positions"]} for i in b.images],
        "kills": [{"t": x["t"], "x": x["x"], "y": x["y"],
                   "allie": next((j.equipe == moi.equipe for j in b.joueurs if j.id == x["victime"]), False)} for x in b.kills],
        "objectifs": [{"t": o["t"], "x": o["x"], "y": o["y"], "nom": o["nom"], "allie": o["equipe"] == moi.equipe} for o in b.objectifs],
    })
    sauts = "".join(
        f'<button class="voir saut {m.genre}" data-t="{m.t:.0f}" data-x="{m.x:.0f}" data-y="{m.y:.0f}">'
        f"<b>{_temps(m.t)}</b> {h(m.titre)}</button>"
        for m in b.moments
    )
    contre = f" · contre {h(b.adversaire.champion)}" if b.adversaire else ""
    revue = f"""<section id="revue"><h2>Revue de carte</h2>
<p class="note">La position des dix joueurs, relevée chaque minute et lissée entre deux relevés. Les croix sont les kills, à leur endroit exact.</p>
<div class="revue">
  <div class="carte" id="carte" style="background-image:url({img('carte', 'map11')})">{pions}<div id="marques"></div></div>
  <div class="cote">
    <div class="commandes"><button id="lecture" aria-label="Lire">▶</button>
      <input type="range" id="temps" min="0" max="{b.duree}" step="1" value="0" aria-label="Moment de la partie"><output id="heure">0:00</output></div>
    <ul class="legende"><li><i class="pastille moi"></i>Toi</li><li><i class="pastille allie"></i>Ton équipe</li>
      <li><i class="pastille ennemi"></i>Adversaires</li><li><i class="croix allie">✕</i>Allié tué</li><li><i class="croix ennemi">✕</i>Ennemi tué</li></ul>
    <div id="fil" class="fil" aria-live="polite"></div>
    <h3 class="titre-sauts">Aller à un moment</h3>
    <div class="sauts">{sauts}</div>
  </div>
</div></section>""" if a_carte else (
        '<section id="revue"><h2>Revue de carte</h2><p class="note">Pas de carte pour cette partie : les positions des '
        "joueurs ne sont gardées que par le client League, pour les parties classées et normales.</p></section>"
    )
    section_coach = f'<section id="coach"><h2>Ce que le coach a dit</h2>{coach}</section>' if coach else ""
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Après-match · {h(moi.champion)}</title><style>{_STYLE}</style></head>
<body>
<header class="hero" style="--illustration:url({img('splash', moi.cle)})">
  <div class="dedans">
    <div class="resultat {classe_resultat}">{resultat}</div>
    <h1>{h(moi.champion)}</h1>
    <p class="sous">{h(b.file)} · {_temps(b.duree)} · {_date(b.date)}{contre}</p>
    <div class="kda-geant">{moi.kills}<i>/</i>{moi.morts}<i>/</i>{moi.assists}</div>
    <div class="tuiles">{tuiles}</div>
  </div>
</header>
<main>
<section id="ameliorer"><h2>À améliorer</h2><ol class="lecons">{lecons}</ol>{forts}</section>
<section id="moments"><h2>Moments clés</h2>
<p class="note">Chaque mort, avec ceux qui l'ont causée et ce qu'il fallait faire{", et chaque objectif joué sans toi. Le bouton montre la carte à cet instant" if a_carte else ""}.</p>
{_moments(b, img, a_carte)}</section>
{revue}
<section id="tableau"><h2>Les dix joueurs</h2><div class="defile">{_tableau(b, img)}</div></section>
{_courbe(b)}
{section_coach}
</main>
<script type="application/json" id="donnees-carte">{carte}</script>{_SCRIPT}</body></html>"""


def generer(b: Bilan, c: Reglages, dossier: Path = RACINE / "rapports", coach: str = "") -> Path:
    dossier.mkdir(parents=True, exist_ok=True)
    page = dossier / f"apres-match_{b.date}_{b.moi.cle}_{b.identifiant}.html"
    page.write_text(rendre(b, c, dossier, coach), encoding="utf-8")
    return page


def creer(client: ClientLol, c: Reglages, identifiant: int | None = None, dossier: Path = RACINE / "rapports",
          coach: str = "") -> Path | None:
    """Analyse une partie de l'historique et écrit sa page. None si le client ne la donne pas."""
    trouve = charger(client, identifiant)
    if trouve is None:
        return None
    partie, chrono, puuid = trouve
    return generer(analyser(partie, chrono, puuid, c), c, dossier, coach)


def coach_dit(enregistrement: Path, c: Reglages) -> str:
    """Ce que le coach a dit pendant la partie enregistrée, mis en page."""
    return debrief._timeline(debrief.analyser(enregistrement, c), c)


def creer_depuis_coach(enregistrement: Path, c: Reglages, dossier: Path = RACINE / "rapports") -> Path:
    """La page d'une partie que le client League ne connaît pas, tirée de l'enregistrement du coach."""
    bruts = list(relire(enregistrement))
    etats = [e for e in map(depuis_json, bruts) if e]
    if not etats:
        raise ValueError(f"enregistrement vide ou illisible : {enregistrement}")
    fin = next((ev for ev in bruts[-1]["events"]["Events"] if ev.get("EventName") == "GameEnd"), None)
    victoire = None if fin is None else fin.get("Result") == "Win"
    jour, _, heure = enregistrement.name.removesuffix(".jsonl.gz").partition("_")
    identifiant = int("".join(chiffre for chiffre in heure.split("_")[0] if chiffre.isdigit()) or 0)
    bilan = depuis_enregistrement(etats, victoire, c, identifiant, jour)
    return generer(bilan, c, dossier, coach_dit(enregistrement, c))


def ouvrir(page: Path) -> None:
    """Ouvre la page dans une fenêtre à elle, sans barre d'adresse ; à défaut, dans le navigateur."""
    navigateur = next((n for n in NAVIGATEURS if n.exists()), None)
    if navigateur:
        subprocess.Popen([str(navigateur), f"--app={page.as_uri()}", "--window-size=1320,940"])
    else:
        os.startfile(page)


_STYLE = """
:root {
  color-scheme: dark;
  --fond: #0a0d13; --surface: #121723; --surface-2: #1a2130; --bord: rgba(255,255,255,.08);
  --encre: #f2f4f8; --encre-2: #b5bdca; --discret: #7b8494; --grille: #232b3a;
  --or: #e2b95b; --allie: #4c9aff; --ennemi: #ff5c6c; --bien: #45c9a0;
  --serie-1: #3987e5; --serie-2: #d95926;
  --e1: 4px; --e2: 8px; --e3: 12px; --e4: 16px; --e5: 24px; --e6: 32px; --e7: 48px;
  --rayon: 14px; --rayon-2: 8px;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--fond); color: var(--encre); font: 15px/1.5 system-ui, "Segoe UI", sans-serif; }
h1, h2, h3, p { margin: 0; }
i { font-style: normal; }
main { max-width: 1120px; margin: 0 auto; padding: var(--e6) var(--e5) var(--e7); }
section { margin-bottom: var(--e7); }
h2 { font-size: 22px; font-weight: 600; margin-bottom: var(--e3); }
.note { color: var(--encre-2); font-size: 13px; margin-bottom: var(--e4); max-width: 70ch; }

.hero { position: relative; min-height: 380px; display: flex; align-items: flex-end;
  background: linear-gradient(90deg, var(--fond) 0%, rgba(10,13,19,.9) 30%, rgba(10,13,19,.15) 68%, rgba(10,13,19,.45) 100%),
              linear-gradient(0deg, var(--fond) 0%, rgba(10,13,19,0) 45%),
              var(--illustration) right 18% / cover no-repeat, var(--surface); }
.dedans { width: 100%; max-width: 1120px; margin: 0 auto; padding: var(--e7) var(--e5) var(--e5); }
.resultat { display: inline-block; font-size: 13px; font-weight: 600; letter-spacing: .12em; text-transform: uppercase;
  padding: var(--e1) var(--e3); border-radius: 999px; border: 1px solid currentColor; }
.resultat.victoire { color: var(--or); } .resultat.defaite { color: var(--ennemi); } .resultat.neutre { color: var(--encre-2); }
h1 { font-size: 56px; line-height: 1.05; font-weight: 700; margin-top: var(--e3); letter-spacing: -.01em; }
.sous { color: var(--encre-2); margin-top: var(--e2); }
.kda-geant { font-size: 28px; font-weight: 600; margin-top: var(--e4); }
.kda-geant i, .kda i { color: var(--discret); margin: 0 .2em; font-weight: 400; }
.tuiles { display: grid; grid-template-columns: repeat(4, minmax(0, 190px)); gap: var(--e3); margin-top: var(--e5); }
.tuile { background: rgba(18,23,35,.78); border: 1px solid var(--bord); border-radius: var(--rayon); padding: var(--e4);
  backdrop-filter: blur(6px); }
.tuile .valeur { font-size: 28px; font-weight: 600; line-height: 1.2; }
.tuile .label { color: var(--encre-2); font-size: 13px; }

.lecons { list-style: none; margin: 0; padding: 0; counter-reset: lecon; display: grid;
  grid-template-columns: repeat(auto-fit, minmax(440px, 1fr)); gap: var(--e3); }
.lecons li { counter-increment: lecon; position: relative; background: var(--surface); border: 1px solid var(--bord);
  border-radius: var(--rayon); padding: var(--e4) var(--e4) var(--e4) 64px; }
.lecons li::before { content: counter(lecon); position: absolute; left: var(--e4); top: var(--e3);
  font-size: 34px; font-weight: 700; color: var(--or); line-height: 1.2; }
.lecons h3 { font-size: 16px; font-weight: 600; }
.lecons .constat { color: var(--encre); margin: var(--e1) 0; }
.lecons p { color: var(--encre-2); }
.forts { list-style: none; display: flex; flex-wrap: wrap; gap: var(--e2); padding: 0; margin: var(--e4) 0 0; }
.forts li { font-size: 13px; color: var(--encre-2); border: 1px solid var(--bord); border-radius: 999px; padding: var(--e1) var(--e3); }
.forts li::before { content: "✓ "; color: var(--bien); font-weight: 600; }

.moment { display: grid; grid-template-columns: 92px 1fr auto; gap: var(--e4); align-items: start;
  background: var(--surface); border: 1px solid var(--bord); border-left: 3px solid var(--discret);
  border-radius: var(--rayon-2); padding: var(--e4); margin-bottom: var(--e2); }
.moment.mort { border-left-color: var(--ennemi); } .moment.exploit { border-left-color: var(--or); }
.moment.objectif { border-left-color: var(--allie); }
.quand { display: grid; gap: 2px; }
.quand time { font-size: 20px; font-weight: 600; font-variant-numeric: tabular-nums; }
.signe { font-size: 16px; } .mort .signe { color: var(--ennemi); } .exploit .signe { color: var(--or); } .objectif .signe { color: var(--allie); }
.genre { font-size: 12px; color: var(--discret); text-transform: uppercase; letter-spacing: .06em; }
.quoi h3 { font-size: 16px; font-weight: 600; }
.quoi p { color: var(--encre-2); }
.quoi .conseil { color: var(--encre); margin-top: var(--e1); }
.acteurs { display: flex; gap: var(--e1); margin: var(--e1) 0; }
.acteur { width: 28px; height: 28px; border-radius: 50%; border: 1.5px solid var(--ennemi); }
.moment.exploit .acteur { border-color: var(--discret); filter: grayscale(.6); }
button { font: inherit; color: var(--encre); background: var(--surface-2); border: 1px solid var(--bord);
  border-radius: var(--rayon-2); padding: var(--e2) var(--e3); cursor: pointer; white-space: nowrap; }
button:hover { background: #232c40; } button:focus-visible, input:focus-visible { outline: 2px solid var(--allie); outline-offset: 2px; }
.rien { color: var(--encre-2); }

.revue { display: grid; grid-template-columns: minmax(280px, 560px) minmax(220px, 1fr); gap: var(--e5); align-items: start; }
.carte { position: relative; aspect-ratio: 1; border-radius: var(--rayon); border: 1px solid var(--bord);
  background-size: cover; overflow: hidden; }
.pion { position: absolute; width: 30px; height: 30px; margin: -15px 0 0 -15px; border-radius: 50%;
  background-size: cover; border: 2px solid var(--ennemi); box-shadow: 0 0 0 1.5px rgba(10,13,19,.9); }
.pion.allie { border-color: var(--allie); }
.pion.moi { width: 38px; height: 38px; margin: -19px 0 0 -19px; border-color: var(--or); z-index: 3; }
.marque { position: absolute; transform: translate(-50%, -50%); font-weight: 700; font-size: 18px; z-index: 4;
  text-shadow: 0 0 3px #000, 0 0 3px #000; pointer-events: none; }
.marque.allie { color: var(--allie); } .marque.ennemi { color: var(--ennemi); }
.marque.objectif { font-size: 12px; color: var(--encre); background: rgba(10,13,19,.85); border: 1px solid var(--bord);
  border-radius: 999px; padding: 1px 8px; text-shadow: none; }
.onde { position: absolute; width: 16px; height: 16px; margin: -8px 0 0 -8px; border-radius: 50%; border: 2px solid var(--or);
  animation: onde 1.2s ease-out 3; pointer-events: none; z-index: 5; }
@keyframes onde { from { transform: scale(1); opacity: 1; } to { transform: scale(6); opacity: 0; } }
@media (prefers-reduced-motion: reduce) { .onde { animation: none; transform: scale(3); } }
.commandes { display: grid; grid-template-columns: auto 1fr auto; gap: var(--e3); align-items: center; }
.commandes output { font-size: 20px; font-weight: 600; font-variant-numeric: tabular-nums; min-width: 3.4em; text-align: right; }
input[type=range] { width: 100%; accent-color: var(--or); }
.legende { list-style: none; padding: 0; margin: var(--e4) 0; display: flex; flex-wrap: wrap; gap: var(--e2) var(--e4);
  font-size: 13px; color: var(--encre-2); }
.legende li { display: inline-flex; align-items: center; gap: var(--e2); }
.pastille { width: 12px; height: 12px; border-radius: 50%; border: 2px solid var(--ennemi); display: inline-block; }
.pastille.allie { border-color: var(--allie); } .pastille.moi { border-color: var(--or); }
.croix { font-weight: 700; } .croix.allie { color: var(--allie); } .croix.ennemi { color: var(--ennemi); }
.fil { font-size: 13px; color: var(--encre-2); display: grid; gap: var(--e1); }
.fil { min-height: 24px; }
.fil b { color: var(--encre); font-variant-numeric: tabular-nums; font-weight: 600; }
.titre-sauts { font-size: 13px; font-weight: 600; color: var(--encre-2); letter-spacing: .06em; text-transform: uppercase; margin: var(--e4) 0 var(--e2); }
.sauts { display: grid; gap: var(--e1); max-height: 330px; overflow-y: auto; }
.saut { text-align: left; white-space: normal; padding: var(--e1) var(--e3); border-left: 3px solid var(--discret); font-size: 13px; color: var(--encre-2); }
.saut b { color: var(--encre); font-variant-numeric: tabular-nums; margin-right: var(--e1); }
.saut.mort { border-left-color: var(--ennemi); } .saut.exploit { border-left-color: var(--or); } .saut.objectif { border-left-color: var(--allie); }

.defile { overflow-x: auto; }
table.equipe { width: 100%; min-width: 900px; table-layout: fixed; border-collapse: collapse; margin-bottom: var(--e5); }
caption { text-align: left; font-size: 13px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase;
  color: var(--encre-2); padding-bottom: var(--e2); }
.equipe.alliee caption { color: var(--allie); } .equipe.adverse caption { color: var(--ennemi); }
.equipe th { text-align: left; font-size: 12px; font-weight: 600; color: var(--discret); padding: var(--e1) var(--e3); }
.equipe td { padding: var(--e2) var(--e3); border-top: 1px solid var(--bord); font-variant-numeric: tabular-nums; }
.equipe tr.moi td { background: rgba(226,185,91,.08); }
.equipe tr.moi td:first-child { box-shadow: inset 3px 0 0 var(--or); }
.qui { display: flex; align-items: center; gap: var(--e3); }
.portrait { width: 36px; height: 36px; border-radius: 50%; border: 1px solid var(--bord); }
.role { display: block; font-size: 12px; color: var(--discret); }
.barre { display: inline-block; width: 90px; height: 6px; border-radius: 3px; background: var(--grille); margin-right: var(--e2);
  vertical-align: middle; overflow: hidden; }
.barre span { display: block; height: 100%; background: var(--encre-2); border-radius: 3px; }
.alliee .barre span { background: var(--allie); } .adverse .barre span { background: var(--ennemi); }
.objets { display: flex; gap: 3px; }
.objets img, .objets .vide { width: 26px; height: 26px; flex: none; border-radius: 5px; border: 1px solid var(--bord); background: var(--surface-2); }

.graphique { margin: 0; background: var(--surface); border: 1px solid var(--bord); border-radius: var(--rayon); padding: var(--e4); }
.cle { display: flex; gap: var(--e4); font-size: 13px; color: var(--encre-2); margin-bottom: var(--e2); }
.cle span { display: inline-flex; align-items: center; gap: var(--e2); }
.trait { width: 18px; height: 2px; display: inline-block; border-radius: 1px; }
.trait.s1 { background: var(--serie-1); } .trait.s2 { background: var(--serie-2); }
.cadre { position: relative; overflow-x: auto; }
.cadre svg { display: block; }
.grille { stroke: var(--grille); stroke-width: 1; }
.graduation { fill: var(--discret); font-size: 12px; font-variant-numeric: tabular-nums; }
.etiquette { fill: var(--encre-2); font-size: 12px; }
.ligne { fill: none; stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
.ligne.s1 { stroke: var(--serie-1); } .ligne.s2 { stroke: var(--serie-2); }
.bout { stroke: var(--surface); stroke-width: 2; } .bout.s1 { fill: var(--serie-1); } .bout.s2 { fill: var(--serie-2); }
.repere { stroke: var(--discret); stroke-width: 1; }
.bulle { position: absolute; top: 0; pointer-events: none; background: var(--surface-2); border: 1px solid var(--bord);
  border-radius: var(--rayon-2); padding: var(--e1) var(--e2); font-size: 13px; white-space: nowrap; }
.bulle b { font-weight: 600; } .bulle div { display: flex; align-items: center; gap: var(--e2); color: var(--encre-2); }
details { margin-top: var(--e3); font-size: 13px; } summary { cursor: pointer; color: var(--encre-2); }
table.donnees { border-collapse: collapse; margin-top: var(--e2); font-variant-numeric: tabular-nums; }
table.donnees th, table.donnees td { text-align: right; padding: var(--e1) var(--e4) var(--e1) 0; }

.timeline { list-style: none; margin: 0; padding: 0; }
#coach h3 { font-size: 13px; font-weight: 600; color: var(--encre-2); margin: var(--e5) 0 var(--e2); letter-spacing: .06em; text-transform: uppercase; }
.timeline li { display: grid; grid-template-columns: 56px 1fr; gap: var(--e2); padding: var(--e2) 0; border-top: 1px solid var(--bord); }
.timeline time { color: var(--discret); font-variant-numeric: tabular-nums; }
.timeline p { color: var(--encre-2); } .timeline strong { color: var(--encre); font-weight: 600; }
.marque-coach, .timeline .marque { position: static; transform: none; font-size: 12px; font-weight: 600; border: 1px solid var(--bord);
  border-radius: 4px; padding: 0 4px; margin-right: 4px; color: var(--ennemi); text-shadow: none; }

@media (max-width: 820px) {
  h1 { font-size: 36px; } .tuiles { grid-template-columns: repeat(2, 1fr); }
  .revue { grid-template-columns: 1fr; } .moment { grid-template-columns: 72px 1fr; } .moment .voir { grid-column: 2; justify-self: start; }
}
"""

_SCRIPT = """<script>
(() => {
  const D = JSON.parse(document.getElementById('donnees-carte').textContent);
  const carte = document.getElementById('carte'), marques = document.getElementById('marques');
  const curseur = document.getElementById('temps'), heure = document.getElementById('heure');
  const lecture = document.getElementById('lecture'), fil = document.getElementById('fil');
  const pions = [...carte.querySelectorAll('.pion')];
  const temps = t => Math.floor(t / 60) + ':' + String(Math.floor(t % 60)).padStart(2, '0');
  const [x0, y0, x1, y1] = D.bords;
  const place = (x, y) => [(x - x0) / (x1 - x0) * 100, (1 - (y - y0) / (y1 - y0)) * 100];

  function position(id, t) {
    let avant = null, apres = null;
    for (const image of D.images) {
      if (!image.p[id]) continue;
      if (image.t <= t) avant = image; else { apres = image; break; }
    }
    if (!avant || !apres) return (avant || apres || {p: {}}).p[id];
    const part = (t - avant.t) / (apres.t - avant.t), a = avant.p[id], b = apres.p[id];
    return [a[0] + (b[0] - a[0]) * part, a[1] + (b[1] - a[1]) * part];
  }

  function montrer(t) {
    t = Math.max(0, Math.min(D.duree, t));
    curseur.value = t; heure.textContent = temps(t);
    for (const pion of pions) {
      const p = position(pion.dataset.id, t);
      pion.hidden = !p;
      if (p) { const [gauche, haut] = place(p[0], p[1]); pion.style.left = gauche + '%'; pion.style.top = haut + '%'; }
    }
    marques.replaceChildren();
    fil.replaceChildren();
    for (const k of D.kills) {
      if (t < k.t || t - k.t > 40) continue;
      const m = document.createElement('div'), [gauche, haut] = place(k.x, k.y);
      m.className = 'marque ' + (k.allie ? 'allie' : 'ennemi'); m.textContent = '✕';
      m.style.left = gauche + '%'; m.style.top = haut + '%'; m.style.opacity = 1 - (t - k.t) / 50;
      marques.append(m);
    }
    for (const o of D.objectifs) {
      if (t < o.t || t - o.t > 40) continue;
      const m = document.createElement('div'), [gauche, haut] = place(o.x, o.y);
      m.className = 'marque objectif'; m.textContent = o.nom;
      m.style.left = gauche + '%'; m.style.top = haut + '%';
      marques.append(m);
    }
    const recents = [...D.kills.map(k => ({t: k.t, texte: k.allie ? 'Un allié est tué' : 'Un ennemi est tué'})),
                     ...D.objectifs.map(o => ({t: o.t, texte: o.nom + (o.allie ? ' pour vous' : ' pour eux')}))]
      .filter(e => e.t <= t && t - e.t <= 90).sort((a, b) => b.t - a.t).slice(0, 5);
    for (const e of recents) {
      const ligne = document.createElement('div'), quand = document.createElement('b');
      quand.textContent = temps(e.t) + ' ';
      ligne.append(quand, e.texte);
      fil.append(ligne);
    }
  }

  let horloge = null;
  function arreter() { clearInterval(horloge); horloge = null; lecture.textContent = '▶'; lecture.setAttribute('aria-label', 'Lire'); }
  lecture.addEventListener('click', () => {
    if (horloge) return arreter();
    if (+curseur.value >= D.duree) montrer(0);
    lecture.textContent = '❚❚'; lecture.setAttribute('aria-label', 'Pause');
    horloge = setInterval(() => {
      const t = +curseur.value + 3;
      montrer(t);
      if (t >= D.duree) arreter();
    }, 50);
  });
  curseur.addEventListener('input', () => { arreter(); montrer(+curseur.value); });
  for (const bouton of document.querySelectorAll('.voir')) {
    bouton.addEventListener('click', () => {
      arreter();
      montrer(+bouton.dataset.t);
      const onde = document.createElement('div'), [gauche, haut] = place(+bouton.dataset.x, +bouton.dataset.y);
      onde.className = 'onde'; onde.style.left = gauche + '%'; onde.style.top = haut + '%';
      marques.append(onde);
      carte.scrollIntoView({behavior: 'smooth', block: 'center'});
    });
  }
  // Un lien « page.html#t=1222 » ouvre la carte à cet instant.
  montrer(+new URLSearchParams(location.hash.slice(1)).get('t') || 0);

  const brut = document.getElementById('donnees-or');
  if (!brut) return;
  const G = JSON.parse(brut.textContent), svg = document.getElementById('courbe'), cadre = document.getElementById('cadre');
  const repere = document.getElementById('repere'), bulle = document.getElementById('bulle');
  let i = -1;
  function lire(n) {
    i = Math.max(0, Math.min(G.moi.length - 1, n));
    const t = G.moi[i][0], x = G.x0 + (G.x1 - G.x0) * t / G.fin;
    repere.setAttribute('x1', x); repere.setAttribute('x2', x); repere.setAttribute('visibility', 'visible');
    bulle.replaceChildren();
    const titre = document.createElement('b'); titre.textContent = temps(t); bulle.append(titre);
    for (const [classe, nom, valeur] of [['s1', 'Toi', G.moi[i][1]], ['s2', G.nom, G.lui[i][1]]]) {
      const ligne = document.createElement('div'), trait = document.createElement('i'), nombre = document.createElement('b');
      trait.className = 'trait ' + classe; nombre.textContent = valeur.toLocaleString('fr-FR');
      ligne.append(trait, nombre, ' ' + nom);
      bulle.append(ligne);
    }
    bulle.hidden = false;
    const gauche = x * svg.getBoundingClientRect().width / svg.viewBox.baseVal.width - cadre.scrollLeft;
    bulle.style.left = (gauche > cadre.clientWidth - 170 ? gauche - bulle.offsetWidth - 12 : gauche + 12) + 'px';
  }
  function cacher() { repere.setAttribute('visibility', 'hidden'); bulle.hidden = true; }
  svg.addEventListener('pointermove', e => {
    const boite = svg.getBoundingClientRect();
    const t = ((e.clientX - boite.left) * svg.viewBox.baseVal.width / boite.width - G.x0) / (G.x1 - G.x0) * G.fin;
    let proche = 0;
    G.moi.forEach((p, n) => { if (Math.abs(p[0] - t) < Math.abs(G.moi[proche][0] - t)) proche = n; });
    lire(proche);
  });
  svg.addEventListener('pointerleave', cacher);
  svg.addEventListener('blur', cacher);
  svg.addEventListener('keydown', e => {
    if (e.key === 'ArrowRight') { lire(i + 1); e.preventDefault(); }
    if (e.key === 'ArrowLeft') { lire(i - 1); e.preventDefault(); }
  });
})();
</script>"""
