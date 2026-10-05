# lol-coach

Coach League of Legends en direct pour ADC. Il lit l'API locale officielle du jeu, te parle en
français pendant la partie et sort un débrief à la fin.

## Lancer

```
lancer.bat
```

Le coach démarre sans fenêtre de terminal : seule la messagerie apparaît, en haut à gauche, avec
une pastille « Coach prêt » tant qu'il attend une partie. Lance-le avant ou pendant la partie : il
la détecte, coache, ouvre l'après-match à la fin et attend la suivante. `arreter.bat` l'arrête.
Ce qu'il dit est aussi écrit dans `journal.log`.

Avec un terminal, pour voir le journal en direct : `python -m lolcoach` (Ctrl+C pour arrêter).

Pour voir ce que ça donne sans lancer le jeu (partie de démonstration, environ deux minutes) :

```
python -m lolcoach --simulation
```

| Option | Effet |
|---|---|
| `--simulation` | joue la partie de démonstration |
| `--vitesse 30` | accélère la simulation (défaut : 10) |
| `--muet` | sans la voix |
| `--sans-fenetre` | sans la messagerie en jeu |
| `--apres-match` | ouvre l'après-match de ta dernière partie ; `--apres-match 8003015310` pour une partie précise |
| `--debrief parties/xxx.jsonl.gz` | refait l'après-match d'une partie enregistrée par le coach |
| `--maj-donnees` | télécharge objets et champions du dernier patch (à relancer après un patch) |

Il faut Python 3.12. Le coach lui-même n'utilise que la bibliothèque standard ; la messagerie
en jeu demande Qt :

```
python -m pip install -r requirements.txt
```

La voix utilise les voix françaises de Windows, par PowerShell 7.

## Régler

Tout est dans `config.toml` : niveau de conseil (`coach`, `faits`, `silencieux`), voix (nom,
hauteur, débit, volume), messagerie (coin de l'écran, durée des bulles), touches des minuteurs,
seuils (or de recall, PV, farm, délais d'annonce).

La messagerie ne passe au-dessus du jeu qu'en mode **fenêtré sans bordure**. Une bulle s'efface
après quelques secondes, ou dès que tu as suivi le conseil (achat fait, ward posée, PV remontés).

## Build et compositions

Au début de la partie, le coach lit les dix champions : plan de lane selon le matchup, build type
de ton champion, objets que la compo adverse fera acheter (anti-soin, Ceinture de mercure,
pénétration d'armure, bottes défensives).

Pendant la partie, le prochain objet se recalcule en continu d'après ce qui se passe : qui est
nourri en face, qui a acheté de l'armure, qui soigne, ce que ton équipe t'offre comme protection.
Le coach en parle quand ça sert :

- à chaque mort, ce qu'il faut prendre à la boutique avec l'or que tu as ;
- quand il te dit de back, et quand ton or termine l'objet visé ;
- juste après un achat, l'objet suivant ;
- en cours de partie, « Change de plan : X avant Y » avec la raison, dès que la partie l'impose.

Le premier objet reste celui du champion. Ensuite, plus le build avance, plus tôt un objet de
situation passe devant. Le détail des règles est dans `docs/CONNAISSANCES.md`, section 12.

Les classes des champions et les prix viennent de données publiques, mises en cache dans
`donnees/` (`--maj-donnees`). Les listes fines et les chemins d'items sont tenus à la main dans
`donnees/champions_notes.toml` : ce sont des repères par famille d'ADC, pas des statistiques du
patch. Corrige-les quand la méta bouge.

## Après-match

À la fin d'une partie, une fenêtre s'ouvre avec le récapitulatif :

- **À améliorer** : les quatre erreurs qui ont coûté le plus, chiffrées (morts loin de l'équipe,
  recalls tardifs, lane perdue, vision, dégâts, présence aux objectifs).
- **Moments clés** : chaque mort, classée (gank, isolé, infériorité numérique, trop avancé...),
  avec qui t'a tué, à combien contre combien, et ce qu'il fallait faire ; les objectifs joués sans
  toi ; tes bons combats.
- **Revue de carte** : la position des dix joueurs rejouée sur la carte, avec les kills à leur
  endroit exact. Chaque moment clé a un bouton qui amène la carte à cet instant.
- **Les dix joueurs** : portraits, K/D/A, sbires, or, dégâts, vision et objets.
- **Or total** : toi et l'ADC adverse, minute par minute.
- **Ce que le coach a dit** pendant la partie, s'il tournait.

La page complète vient du client League, qui doit être ouvert : il garde tes parties classées et
normales. Pour l'outil d'entraînement, ou si le client ne répond pas dans les deux minutes, la
même page est tirée de l'enregistrement du coach : tout y est sauf la carte et les dégâts.

Limite : les positions sont relevées une fois par minute et lissées entre deux relevés. La carte
montre où chacun était, pas ce que tu voyais sur ta minimap.

## Minuteurs de sorts ennemis

Le coach ne voit ni tes pings ni le chat. Quand tu vois partir un sort d'invocateur, appuie sur
la touche de cet ennemi, en plus de ton ping :

| Ennemi (ordre du tableau des scores) | Son Flash | Son autre sort |
|---|---|---|
| Top | Ctrl+F1 | Shift+F1 |
| Jungle | Ctrl+F2 | Shift+F2 |
| Mid | Ctrl+F3 | Shift+F3 |
| ADC | Ctrl+F4 | Shift+F4 |
| Support | Ctrl+F5 | Shift+F5 |

Il confirme à la voix (« Flash de Leona noté, retour à 15 minutes »), affiche le décompte dans
la fenêtre, prévient 30 secondes avant le retour, puis au retour. Deux appuis en moins de
10 secondes annulent. Les bottes de lucidité de l'ennemi sont prises en compte. Le jeu ne montre
pas la rune Perspicacité cosmique : si l'ennemi a l'arbre Inspiration, le coach la suppose et
annonce un retour « au plus tôt ».

Ces touches ne sont prises à Windows que pendant une partie, et se changent dans `config.toml`.

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
- `lolcoach/bilan.py` et `lolcoach/apres_match.py` : l'analyse et la page d'après-match.
- `lolcoach/regles.py` : les fondamentaux. `lolcoach/strategie.py` : matchup, build, macro avancée.
- `lolcoach/achats.py` : le prochain objet à acheter, selon le champion et l'état de la partie.
- `donnees/champions_notes.toml` : soigneurs, accroches, ultis d'engage, chemins d'items par famille.

## Tests

```
python -m unittest discover -s tests
```
