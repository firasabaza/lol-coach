# lol-coach

Coach League of Legends en direct pour ADC. Il lit l'API locale officielle du jeu, te parle en
français pendant la partie et sort un débrief à la fin.

## Lancer

```
lancer.bat
```

ou `python -m lolcoach`. Lance-le avant ou pendant la partie : il attend, détecte la partie,
coache, puis écrit le débrief dans `rapports/` et attend la suivante. Ctrl+C pour arrêter.

Pour voir ce que ça donne sans lancer le jeu (partie de démonstration, environ deux minutes) :

```
python -m lolcoach --simulation
```

| Option | Effet |
|---|---|
| `--simulation` | joue la partie de démonstration |
| `--vitesse 30` | accélère la simulation (défaut : 10) |
| `--muet` | sans la voix |
| `--sans-fenetre` | sans la mini fenêtre |
| `--debrief parties/xxx.jsonl.gz` | refait le rapport d'une partie enregistrée |

Rien à installer : Python 3.12 et sa bibliothèque standard. La voix utilise les voix françaises
de Windows, par PowerShell 7.

## Régler

Tout est dans `config.toml` : niveau de conseil (`coach`, `faits`, `silencieux`), voix, position
de la fenêtre, seuils (or de recall, PV, farm, délais d'annonce).

La mini fenêtre ne passe au-dessus du jeu qu'en mode **fenêtré sans bordure**.

## Ce que le coach voit, et ce qu'il ne voit pas

Il voit ce que donne la Live Client Data API : l'horloge, ton or, tes PV, les niveaux, objets,
KDA, sbires et score de vision des dix joueurs, les morts et les événements (drakes, Herald,
Baron, tours, kills).

Il ne voit ni la minimap, ni les positions, ni l'état des vagues. Ses conseils de wave reposent
sur l'horloge des vagues canon, et sa lecture du jungler adverse sur les kills, les niveaux et les
fenêtres de timing.

## Fichiers

- `SPEC.md` : le projet, les choix, le plan.
- `docs/CONNAISSANCES.md` : ce que le coach sait, avec les sources.
- `donnees/saison.toml` : les timers de la saison. À mettre à jour quand un patch les change.
- `lolcoach/regles.py` : les règles de coaching. C'est là qu'on ajoute un conseil.

## Tests

```
python -m unittest discover -s tests
```
