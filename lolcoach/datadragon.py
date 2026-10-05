"""Données statiques du jeu : objets (Data Dragon, Riot) et champions (Meraki Analytics, données ouvertes).

L'API du jeu ne donne, dans `price`, que le coût de combinaison d'un objet, et rien sur la nature
des champions. Ces données viennent d'ici et sont mises en cache dans donnees/.

    python -m lolcoach --maj-donnees    à relancer après un patch
"""

from __future__ import annotations

import json
import urllib.request
from functools import cache
from pathlib import Path

from .reglages import RACINE

DDRAGON = "https://ddragon.leagueoflegends.com"
MERAKI = "https://cdn.merakianalytics.com/riot/lol/resources/latest/en-US/champions.json"
OBJETS = RACINE / "donnees" / "objets.json"
CHAMPIONS = RACINE / "donnees" / "champions.json"
IMAGES = RACINE / "donnees" / "images"
FAILLE = "11"  # identifiant de la Faille de l'invocateur dans Data Dragon


def _lire(url: str):
    requete = urllib.request.Request(url, headers={"User-Agent": "lol-coach"})
    with urllib.request.urlopen(requete, timeout=40) as reponse:
        return json.load(reponse)


def mettre_a_jour(objets: Path = OBJETS, champions: Path = CHAMPIONS) -> str:
    """Télécharge objets et champions du dernier patch. Rend le numéro du patch."""
    patch = _lire(f"{DDRAGON}/api/versions.json")[0]
    bruts = _lire(f"{DDRAGON}/cdn/{patch}/data/fr_FR/item.json")["data"]
    table = {
        identifiant: {
            "nom": o["name"], "prix": o["gold"]["total"], "achetable": o["gold"]["purchasable"],
            "recette": [int(c) for c in o.get("from", [])],
            "armure": o.get("stats", {}).get("FlatArmorMod", 0),
            "rm": o.get("stats", {}).get("FlatSpellBlockMod", 0),
            "etiquettes": o.get("tags", []),
        }
        for identifiant, o in sorted(bruts.items(), key=lambda o: int(o[0]))
        if o.get("maps", {}).get(FAILLE)
    }
    objets.write_text(json.dumps({"patch": patch, "objets": table}, ensure_ascii=False, indent=0), encoding="utf-8")

    # Noms français et temps de recharge des sorts : un seul fichier pour tous les champions.
    complets = {cle.lower(): c for cle, c in _lire(f"{DDRAGON}/cdn/{patch}/data/fr_FR/championFull.json")["data"].items()}

    def sorts(cle: str) -> dict:
        return {
            lettre: {"nom": sort["name"], "recharge": sort["cooldown"][0]}
            for lettre, sort in zip("QWER", complets.get(cle.lower(), {}).get("spells", []))
        }

    runes: dict[str, str] = {}
    fiches = {
        cle: {
            "id": c["id"],
            "sorts": sorts(cle),
            "nom": c["name"],
            "roles": c.get("roles", []),
            "degats": "AP" if c.get("adaptiveType") == "MAGIC_DAMAGE" else "AD",
            "portee": int(c["stats"]["attackRange"]["flat"]),
            "melee": c.get("attackType") == "MELEE",
            "notes": {k: c.get("attributeRatings", {}).get(k, 0) for k in ("damage", "toughness", "control", "mobility")},
        }
        for cle, c in sorted(_lire(MERAKI).items())
    }
    arbres = _lire(f"{DDRAGON}/cdn/{patch}/data/fr_FR/runesReforged.json")
    for arbre in arbres:
        for rune in arbre["slots"][0]["runes"]:
            runes[str(rune["id"])] = rune["name"]
    champions.write_text(
        json.dumps({"patch": patch, "champions": fiches, "runes": runes}, ensure_ascii=False, indent=0), encoding="utf-8"
    )
    return patch


def _cache(chemin: Path, cle: str) -> dict:
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))[cle]
    except (OSError, ValueError, KeyError):
        return {}


@cache
def objets() -> dict[int, dict]:
    """Identifiant d'objet -> {nom, prix total, achetable, recette, armure, rm, etiquettes}. Vide si le cache manque."""
    return {int(i): o for i, o in _cache(OBJETS, "objets").items()}


@cache
def champions() -> dict[str, dict]:
    """Clé du champion (« Kaisa ») -> {id, nom, roles, degats, portee, melee, notes, sorts}. Vide si le cache manque."""
    return _cache(CHAMPIONS, "champions")


@cache
def runes() -> dict[int, str]:
    """Identifiant d'une rune principale -> son nom français."""
    return {int(i): nom for i, nom in _cache(CHAMPIONS, "runes").items()}


@cache
def champion_par_id(identifiant: int) -> tuple[str, dict]:
    """(clé, fiche) du champion qui porte ce numéro ; ("", {}) s'il est inconnu."""
    return next(((cle, f) for cle, f in champions().items() if f.get("id") == identifiant), ("", {}))


@cache
def image(genre: str, nom: str) -> Path | None:
    """Chemin local d'une image du jeu, téléchargée depuis Data Dragon à la première demande.

    genre : "champion" (portrait carré), "splash" (illustration), "objet", "carte".
    """
    patch = json.loads(OBJETS.read_text(encoding="utf-8")).get("patch", "") if OBJETS.exists() else ""
    adresses = {
        "champion": (f"{DDRAGON}/cdn/{patch}/img/champion/{nom}.png", "png"),
        "splash": (f"{DDRAGON}/cdn/img/champion/splash/{nom}_0.jpg", "jpg"),
        "objet": (f"{DDRAGON}/cdn/{patch}/img/item/{nom}.png", "png"),
        "carte": (f"{DDRAGON}/cdn/{patch}/img/map/map11.png", "png"),
    }
    adresse, extension = adresses[genre]
    fichier = IMAGES / genre / f"{nom}.{extension}"
    if not fichier.exists():
        try:
            requete = urllib.request.Request(adresse, headers={"User-Agent": "lol-coach"})
            with urllib.request.urlopen(requete, timeout=20) as reponse:
                contenu = reponse.read()
        except OSError:
            return None
        fichier.parent.mkdir(parents=True, exist_ok=True)
        fichier.write_bytes(contenu)
    return fichier
