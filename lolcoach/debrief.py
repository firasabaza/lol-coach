"""Rejoue une partie enregistrée dans le moteur et en tire un rapport HTML autonome."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from html import escape as h
from pathlib import Path

from .enregistreur import relire
from .etat import Etat, depuis_json
from .moteur import Moteur
from .reglages import RACINE, Reglages
from .regles import URGENT, Conseil, duree, or_en_poche

PAS = 5  # secondes entre deux points du graphique
OR_PAR_SBIRE = 20


@dataclass
class Mort:
    t: float
    or_: float
    tueurs: list[str]
    sans_jungler: float


@dataclass
class Analyse:
    champion: str = ""
    adversaires: str = ""
    duree: float = 0.0
    kda: tuple[int, int, int] = (0, 0, 0)
    cs: int = 0
    points: list[tuple[float, float, int]] = field(default_factory=list)  # (t, or, sbires)
    conseils: list[tuple[float, Conseil]] = field(default_factory=list)
    achats: list[tuple[float, float]] = field(default_factory=list)  # (t, or juste avant)
    morts: list[Mort] = field(default_factory=list)
    or_dormant: float = 0.0
    trou_vision: float = 0.0


def analyser(chemin: Path, reglages: Reglages) -> Analyse:
    moteur = Moteur(replace(reglages, niveau="coach"))
    a = Analyse()
    precedent: Etat | None = None
    for brut in relire(chemin):
        e = depuis_json(brut)
        if e is None:
            continue
        achats_avant = moteur.suivi.nb_achats
        for conseil in moteur.lire(e):
            a.conseils.append((e.t, conseil))
        s = moteur.suivi

        if precedent is None:
            adc, sup = e.ennemi("BOTTOM"), e.ennemi("UTILITY")
            a.champion = e.moi.champion
            a.adversaires = " et ".join(j.champion for j in (adc, sup) if j)
        else:
            if s.nb_achats > achats_avant:
                a.achats.append((e.t, precedent.or_))
            if or_en_poche(precedent) >= reglages.seuils.or_recall and not precedent.moi.mort:
                a.or_dormant += e.t - precedent.t
        if s.mort_ce_tour:
            fatal = next((ev for ev in reversed(e.evenements) if ev.victime == e.moi.nom), None)
            noms = [fatal.tueur, *fatal.assistants] if fatal else []
            tueurs = [j.champion if (j := e.joueur(n)) else n for n in noms]
            a.morts.append(Mort(e.t, e.or_, tueurs, e.t - s.jungler_nouvelle))
        if e.t > 120 and not e.moi.mort:
            a.trou_vision = max(a.trou_vision, e.t - s.derniere_vision)
        if not a.points or e.t - a.points[-1][0] >= PAS:
            a.points.append((e.t, e.or_, e.moi.cs))

        a.duree, a.cs = e.t, e.moi.cs
        a.kda = (e.moi.kills, e.moi.morts, e.moi.assists)
        precedent = e
    return a


def _temps(t: float) -> str:
    return f"{int(t) // 60}:{int(t) % 60:02d}"


def _nombre(n: float) -> str:
    return f"{round(n):,}".replace(",", " ")


def _decimal(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def _lecons(a: Analyse, c: Reglages) -> list[str]:
    """Les points à travailler, du plus coûteux au moins coûteux."""
    minutes = a.duree / 60
    notes: list[tuple[float, str]] = []

    rythme = a.cs / minutes
    if rythme < c.seuils.cs_par_minute:
        manque = (c.seuils.cs_par_minute - rythme) * minutes * OR_PAR_SBIRE
        notes.append((manque / 100, (
            f"<strong>Farm.</strong> {_decimal(rythme)} sbires par minute pour un objectif de "
            f"{c.seuils.cs_par_minute:g} : environ {_nombre(round(manque, -2))} gold laissés sur la carte."
        )))
    if a.or_dormant >= 60:
        notes.append((a.or_dormant / 20, (
            f"<strong>Recalls.</strong> {duree(a.or_dormant)} jouées avec plus de "
            f"{_nombre(c.seuils.or_recall)} gold en poche. Crash la vague et reset plus tôt."
        )))
    if a.trou_vision >= c.seuils.vision_silence:
        notes.append((a.trou_vision / 40, (
            f"<strong>Vision.</strong> Jusqu'à {duree(round(a.trou_vision / 10) * 10)} sans rien poser. "
            "Le trinket se pose dès qu'il est disponible."
        )))
    riches = [m for m in a.morts if m.or_ >= 0.8 * c.seuils.or_recall]
    if riches:
        pluriel = "s" if len(riches) > 1 else ""
        notes.append((8 * len(riches), (
            f"<strong>Morts évitables.</strong> {len(riches)} mort{pluriel} avec un back en poche "
            f"({_nombre(max(m.or_ for m in riches))} gold). Ce gold devait être dépensé avant."
        )))
    en_retard = sorted(cle.rsplit("-", 1)[1] for _, k in a.conseils if (cle := k.cle).startswith("niveau-eux-"))
    if en_retard:
        notes.append((3 * len(en_retard), (
            f"<strong>Niveaux.</strong> Ils ont eu le niveau {' et le niveau '.join(en_retard)} avant toi. "
            "Pousse la première vague pour prendre le niveau 2."
        )))
    return [texte for _, texte in sorted(notes, key=lambda n: -n[0])][:3]


def _tuile(label: str, valeur: str, detail: str, bien: bool) -> str:
    etat = ("bien", "✓", "Bien") if bien else ("a-revoir", "●", "À travailler")
    return (
        f'<div class="tuile"><div class="label">{h(label)}</div><div class="valeur">{h(valeur)}</div>'
        f'<div class="detail">{h(detail)}</div>'
        f'<div class="etat {etat[0]}"><span aria-hidden="true">{etat[1]}</span> {etat[2]}</div></div>'
    )


def _graphique(a: Analyse, c: Reglages) -> str:
    largeur, hauteur = 760, 250
    gauche, droite, haut, bas = 52, 16, 16, 30
    seuil = c.seuils.or_recall
    y_max = max(1500, -(-max(p[1] for p in a.points) // 500) * 500)

    def x(t: float) -> float:
        return gauche + (largeur - gauche - droite) * t / a.duree

    def y(v: float) -> float:
        return haut + (hauteur - haut - bas) * (1 - v / y_max)

    svg: list[str] = []
    for palier in range(0, int(y_max) + 1, 500):
        svg.append(f'<line class="grille" x1="{gauche}" x2="{largeur - droite}" y1="{y(palier):.1f}" y2="{y(palier):.1f}"/>')
        svg.append(f'<text class="graduation" x="{gauche - 8}" y="{y(palier) + 4:.1f}" text-anchor="end">{_nombre(palier)}</text>')
    pas_x = 300 if a.duree >= 600 else 120
    for t in range(0, int(a.duree) + 1, pas_x):
        svg.append(f'<text class="graduation" x="{x(t):.1f}" y="{hauteur - 8}" text-anchor="middle">{_temps(t)}</text>')
    svg.append(f'<line class="axe" x1="{gauche}" x2="{largeur - droite}" y1="{y(0):.1f}" y2="{y(0):.1f}"/>')

    svg.append(f'<line class="seuil" x1="{gauche}" x2="{largeur - droite}" y1="{y(seuil):.1f}" y2="{y(seuil):.1f}"/>')
    svg.append(f'<text class="graduation" x="{largeur - droite}" y="{y(seuil) - 6:.1f}" text-anchor="end">Seuil de recall · {_nombre(seuil)}</text>')

    trace = " ".join(f"{x(t):.1f},{y(v):.1f}" for t, v, _ in a.points)
    svg.append(f'<polygon class="aire" points="{x(a.points[0][0]):.1f},{y(0):.1f} {trace} {x(a.points[-1][0]):.1f},{y(0):.1f}"/>')
    svg.append(f'<polyline class="ligne" points="{trace}"/>')

    for t, avant in a.achats:
        svg.append(f'<circle class="achat" cx="{x(t):.1f}" cy="{y(avant):.1f}" r="4.5"><title>Achat à {_temps(t)}</title></circle>')
    for m in a.morts:
        cx, cy = x(m.t), y(m.or_)
        svg.append(
            f'<g class="mort"><title>Mort à {_temps(m.t)}</title><circle cx="{cx:.1f}" cy="{cy:.1f}" r="8"/>'
            f'<path d="M{cx - 4:.1f} {cy - 4:.1f}l8 8m0 -8l-8 8"/></g>'
        )
    svg.append('<line class="repere" id="repere" y1="16" y2="220" visibility="hidden"/>')
    svg.append('<circle class="curseur" id="curseur" r="4.5" visibility="hidden"/>')

    donnees = json.dumps({
        "points": [[round(t), round(v)] for t, v, _ in a.points],
        "x0": gauche, "x1": largeur - droite, "y0": y(0), "y1": y(y_max), "yMax": y_max, "duree": a.duree,
    }).replace("</", "<\\/")
    lignes = "".join(
        f"<tr><td>{_temps(t)}</td><td>{_nombre(v)}</td><td>{cs}</td></tr>"
        for t, v, cs in a.points if round(t) % 60 < PAS
    )
    return f"""
<figure class="graphique">
  <div class="cle"><span><svg width="12" height="12"><circle class="achat" cx="6" cy="6" r="4.5"/></svg> Achat</span>
    <span><svg width="16" height="16" class="mort"><circle cx="8" cy="8" r="7"/><path d="M4 4l8 8m0 -8l-8 8"/></svg> Mort</span></div>
  <div class="cadre" id="cadre">
    <svg viewBox="0 0 {largeur} {hauteur}" width="{largeur}" height="{hauteur}" role="img" tabindex="0" id="courbe"
         aria-label="Or en poche au fil de la partie. Flèches gauche et droite pour parcourir.">{''.join(svg)}</svg>
    <div class="bulle" id="bulle" hidden><strong></strong><span></span></div>
  </div>
  <details><summary>Voir les données</summary>
    <table><thead><tr><th>Temps</th><th>Or en poche</th><th>Sbires</th></tr></thead><tbody>{lignes}</tbody></table>
  </details>
</figure>
<script type="application/json" id="donnees">{donnees}</script>"""


def _timeline(a: Analyse, c: Reglages) -> str:
    fin_lane = c.saison["sbires"]["fin_de_lane"]
    phases = [("Phase de lane", 0, fin_lane), ("Milieu de partie", fin_lane, 1500), ("Fin de partie", 1500, float("inf"))]
    lignes: list[tuple[float, str]] = []
    for t, k in a.conseils:
        marque = '<span class="marque urgent">Urgent</span> ' if k.priorite == URGENT else ""
        fait = f"<strong>{h(k.fait)}</strong> " if k.fait else ""
        lignes.append((t, f'<li><time>{_temps(t)}</time><p>{marque}{fait}{h(k.action)}</p></li>'))
    for m in a.morts:
        par = f"Tué par {h(m.tueurs[0])}" + (f" avec {h(', '.join(m.tueurs[1:]))}" if len(m.tueurs) > 1 else "") if m.tueurs else "Mort"
        contexte = f"{_nombre(m.or_)} gold en poche"
        if m.sans_jungler > 45:
            contexte += f", leur jungler pas vu depuis {duree(round(m.sans_jungler / 5) * 5)}"
        lignes.append((m.t - 0.1, (
            f'<li class="mort"><time>{_temps(m.t)}</time><p><span class="marque mort">✕ Mort</span> '
            f"<strong>{par}.</strong> {contexte}.</p></li>"
        )))
    lignes.sort(key=lambda ligne: ligne[0])

    blocs = []
    for nom, debut, fin in phases:
        dans = [html for t, html in lignes if debut <= t < fin]
        if dans:
            blocs.append(f"<h3>{nom}</h3><ol class=\"timeline\">{''.join(dans)}</ol>")
    return "".join(blocs)


def rendre(a: Analyse, c: Reglages, date: str) -> str:
    titre = f"{a.champion} contre {a.adversaires}" if a.adversaires else a.champion
    if a.duree < 180 or len(a.points) < 2:
        corps = '<p class="vide">Partie trop courte pour un débrief. Il faut au moins trois minutes de jeu.</p>'
        script = ""
    else:
        minutes = a.duree / 60
        rythme = a.cs / minutes
        riches = sum(m.or_ >= 0.8 * c.seuils.or_recall for m in a.morts)
        lecons = _lecons(a, c)
        liste = "".join(f"<li>{texte}</li>" for texte in lecons) or "<li>Rien de majeur à corriger sur cette partie.</li>"
        tuiles = "".join([
            _tuile("Farm", f"{_decimal(rythme)} / min", f"objectif {c.seuils.cs_par_minute:g}", rythme >= c.seuils.cs_par_minute),
            _tuile("Or dormant", duree(a.or_dormant).replace(" secondes", " s").replace("une minute", "1 min").replace(" minutes", " min"),
                   f"avec plus de {_nombre(c.seuils.or_recall)} gold", a.or_dormant < 60),
            _tuile("Plus long trou de vision", _temps(a.trou_vision), "sans rien poser", a.trou_vision < c.seuils.vision_silence),
            _tuile("Morts", str(len(a.morts)), f"dont {riches} avec un back en poche" if riches else "aucune évitable", riches == 0),
        ])
        corps = f"""
<section><h2>À travailler</h2><ol class="lecons">{liste}</ol></section>
<section class="tuiles">{tuiles}</section>
<section><h2>Or en poche</h2>
  <p class="note">Chaque passage au-dessus du seuil est un back que tu pouvais prendre.</p>{_graphique(a, c)}</section>
<section><h2>Ce que le coach a dit</h2>{_timeline(a, c)}</section>"""
        script = _SCRIPT
    k, d, s = a.kda
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Débrief · {h(titre)}</title><style>{_STYLE}</style></head>
<body><main>
<header><div class="surtitre">Débrief</div><h1>{h(titre)}</h1>
<p class="meta">{h(date)} · {_temps(a.duree)} · {k}/{d}/{s} · {a.cs} sbires</p></header>
{corps}
</main>{script}</body></html>"""


def generer(chemin: Path, reglages: Reglages, dossier: Path = RACINE / "rapports") -> Path:
    """Écrit le rapport de la partie enregistrée dans `chemin` et rend son emplacement."""
    analyse = analyser(chemin, reglages)
    nom = chemin.name.removesuffix(".jsonl.gz")
    jour, _, heure = nom.partition("_")
    date = f"{'/'.join(reversed(jour.split('-')))} à {heure[:5].replace('h', ':')}" if heure else nom
    dossier.mkdir(parents=True, exist_ok=True)
    rapport = dossier / f"{nom}.html"
    rapport.write_text(rendre(analyse, reglages, date), encoding="utf-8")
    return rapport


_STYLE = """
:root {
  color-scheme: light dark;
  --plan: #f9f9f7; --surface: #fcfcfb; --encre: #0b0b0b; --encre-2: #52514e; --discret: #898781;
  --grille: #e1e0d9; --axe: #c3c2b7; --bord: rgba(11,11,11,.10);
  --serie: #2a78d6; --critique: #d03b3b; --bien: #0ca30c;
  --e1: 4px; --e2: 8px; --e3: 12px; --e4: 16px; --e5: 24px; --e6: 32px; --e7: 48px;
  --rayon: 8px;
}
@media (prefers-color-scheme: dark) {
  :root {
    --plan: #0d0d0d; --surface: #1a1a19; --encre: #ffffff; --encre-2: #c3c2b7;
    --grille: #2c2c2a; --axe: #383835; --bord: rgba(255,255,255,.10); --serie: #3987e5;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--plan); color: var(--encre);
  font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 880px; margin: 0 auto; padding: var(--e7) var(--e4) var(--e7); }
header { margin-bottom: var(--e6); }
.surtitre { font-size: 13px; font-weight: 600; color: var(--encre-2); letter-spacing: .04em; text-transform: uppercase; }
h1 { font-size: 32px; line-height: 1.2; font-weight: 600; margin: var(--e1) 0 var(--e2); }
h2 { font-size: 20px; font-weight: 600; margin: 0 0 var(--e3); }
h3 { font-size: 13px; font-weight: 600; color: var(--encre-2); margin: var(--e5) 0 var(--e2);
  letter-spacing: .04em; text-transform: uppercase; }
.meta, .note { color: var(--encre-2); margin: 0; font-size: 13px; }
.note { margin-bottom: var(--e3); }
section { margin-bottom: var(--e7); }
.vide { color: var(--encre-2); }

.lecons { margin: 0; padding: 0; list-style: none; counter-reset: lecon; }
.lecons li { counter-increment: lecon; position: relative; padding: var(--e3) 0 var(--e3) var(--e7);
  border-top: 1px solid var(--bord); font-size: 17px; }
.lecons li::before { content: counter(lecon); position: absolute; left: 0; top: var(--e2);
  font-size: 32px; line-height: 1.2; font-weight: 600; color: var(--discret); }

.tuiles { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--e3); }
.tuile { background: var(--surface); border: 1px solid var(--bord); border-radius: var(--rayon); padding: var(--e4);
  display: flex; flex-direction: column; }
.label, .detail, .etat { font-size: 13px; color: var(--encre-2); }
.valeur { font-size: 32px; line-height: 1.2; font-weight: 600; margin-top: var(--e1); }
.etat { margin-top: auto; padding-top: var(--e3); }
.etat.bien span { color: var(--bien); }
.etat.a-revoir span { color: var(--critique); }

.graphique { margin: 0; background: var(--surface); border: 1px solid var(--bord); border-radius: var(--rayon); padding: var(--e4); }
.cle { display: flex; gap: var(--e4); font-size: 13px; color: var(--encre-2); margin-bottom: var(--e2); }
.cle span { display: inline-flex; align-items: center; gap: var(--e1); }
.cadre { position: relative; overflow-x: auto; }
.cadre svg { display: block; outline-offset: 2px; }
.grille { stroke: var(--grille); stroke-width: 1; }
.axe, .seuil { stroke: var(--axe); stroke-width: 1; }
.seuil { stroke: var(--encre-2); }
.graduation { fill: var(--discret); font-size: 12px; font-variant-numeric: tabular-nums; }
.ligne { fill: none; stroke: var(--serie); stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
.aire { fill: var(--serie); opacity: .10; }
.achat, .curseur { fill: var(--serie); stroke: var(--surface); stroke-width: 2; }
.mort circle { fill: var(--surface); }
.mort path { stroke: var(--critique); stroke-width: 2; stroke-linecap: round; fill: none; }
.repere { stroke: var(--axe); stroke-width: 1; }
.bulle { position: absolute; top: 0; pointer-events: none; background: var(--surface); border: 1px solid var(--bord);
  border-radius: var(--rayon); padding: var(--e1) var(--e2); font-size: 13px; white-space: nowrap;
  box-shadow: 0 2px 8px rgba(0,0,0,.12); }
.bulle strong { display: block; font-weight: 600; }
.bulle span { color: var(--encre-2); }
details { margin-top: var(--e3); font-size: 13px; }
summary { cursor: pointer; color: var(--encre-2); }
table { border-collapse: collapse; margin-top: var(--e2); font-variant-numeric: tabular-nums; }
th, td { text-align: right; padding: var(--e1) var(--e4) var(--e1) 0; }
th { font-weight: 600; color: var(--encre-2); }

.timeline { list-style: none; margin: 0; padding: 0; }
.timeline li { display: grid; grid-template-columns: 56px 1fr; gap: var(--e2); padding: var(--e2) 0;
  border-top: 1px solid var(--bord); }
.timeline time { color: var(--discret); font-variant-numeric: tabular-nums; }
.timeline p { margin: 0; }
.marque { font-size: 13px; font-weight: 600; border: 1px solid var(--bord); border-radius: var(--e1);
  padding: 0 var(--e1); margin-right: var(--e1); color: var(--encre-2); white-space: nowrap; }
.marque.mort, .marque.urgent { color: var(--critique); }

@media (max-width: 640px) {
  .tuiles { grid-template-columns: repeat(2, 1fr); }
  h1 { font-size: 24px; }
  .lecons li { font-size: 15px; }
}
@media print { body { background: #fff; } .bulle { display: none; } }
"""

_SCRIPT = """<script>
(() => {
  const d = JSON.parse(document.getElementById('donnees').textContent);
  const svg = document.getElementById('courbe'), cadre = document.getElementById('cadre');
  const repere = document.getElementById('repere'), curseur = document.getElementById('curseur');
  const bulle = document.getElementById('bulle');
  const temps = t => Math.floor(t / 60) + ':' + String(t % 60).padStart(2, '0');
  let i = -1;
  function montrer(n) {
    i = Math.max(0, Math.min(d.points.length - 1, n));
    const [t, or] = d.points[i];
    const x = d.x0 + (d.x1 - d.x0) * t / d.duree, y = d.y0 + (d.y1 - d.y0) * or / d.yMax;
    repere.setAttribute('x1', x); repere.setAttribute('x2', x); repere.setAttribute('visibility', 'visible');
    curseur.setAttribute('cx', x); curseur.setAttribute('cy', y); curseur.setAttribute('visibility', 'visible');
    bulle.firstChild.textContent = or.toLocaleString('fr-FR') + ' gold';
    bulle.lastChild.textContent = temps(t);
    bulle.hidden = false;
    const echelle = svg.getBoundingClientRect().width / svg.viewBox.baseVal.width;
    const gauche = x * echelle - cadre.scrollLeft;
    bulle.style.left = (gauche > cadre.clientWidth - 120 ? gauche - bulle.offsetWidth - 12 : gauche + 12) + 'px';
  }
  function cacher() {
    repere.setAttribute('visibility', 'hidden'); curseur.setAttribute('visibility', 'hidden'); bulle.hidden = true;
  }
  svg.addEventListener('pointermove', e => {
    const boite = svg.getBoundingClientRect();
    const x = (e.clientX - boite.left) * svg.viewBox.baseVal.width / boite.width;
    const t = (x - d.x0) / (d.x1 - d.x0) * d.duree;
    let proche = 0;
    d.points.forEach((p, n) => { if (Math.abs(p[0] - t) < Math.abs(d.points[proche][0] - t)) proche = n; });
    montrer(proche);
  });
  svg.addEventListener('pointerleave', cacher);
  svg.addEventListener('blur', cacher);
  svg.addEventListener('keydown', e => {
    if (e.key === 'ArrowRight') { montrer(i + 1); e.preventDefault(); }
    if (e.key === 'ArrowLeft') { montrer(i - 1); e.preventDefault(); }
  });
})();
</script>"""
