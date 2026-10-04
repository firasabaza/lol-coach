"""Prix total des objets, lu dans Data Dragon (les données statiques publiques de Riot).

L'API du jeu ne donne, dans `price`, que le coût de combinaison d'un objet : un objet fini à
3000 gold y vaut quelques centaines. Le vrai prix vient d'ici, mis en cache dans donnees/objets.json.

    python -m lolcoach --maj-donnees    à relancer après un patch
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from .reglages import RACINE

BASE = "https://ddragon.leagueoflegends.com"
CACHE = RACINE / "donnees" / "objets.json"


def _lire(url: str):
    with urllib.request.urlopen(url, timeout=20) as reponse:
        return json.load(reponse)


def mettre_a_jour(cache: Path = CACHE) -> str:
    """Télécharge les prix du dernier patch. Rend le numéro du patch."""
    version = _lire(f"{BASE}/api/versions.json")[0]
    objets = _lire(f"{BASE}/cdn/{version}/data/fr_FR/item.json")["data"]
    prix = {identifiant: objet["gold"]["total"] for identifiant, objet in sorted(objets.items(), key=lambda o: int(o[0]))}
    cache.write_text(json.dumps({"patch": version, "prix": prix}, indent=0), encoding="utf-8")
    return version


def prix_totaux(cache: Path = CACHE) -> dict[int, int]:
    """Identifiant d'objet -> prix total. Vide si le cache manque : on retombe alors sur l'API du jeu."""
    try:
        return {int(i): int(p) for i, p in json.loads(cache.read_text(encoding="utf-8"))["prix"].items()}
    except (OSError, ValueError, KeyError):
        return {}
