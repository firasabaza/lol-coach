# lol-coach

## Pitch

Un coach League of Legends qui suit ta partie en direct par l'API officielle du jeu et te parle
comme un coach haut elo assis derrière toi : quand back, quand pousser, quand décaler au drake,
quand warder, où est probablement leur jungler. Après la partie, il sort un débrief horodaté.

## Utilisateur & usage

Firas, ADC. Scénario type :

1. Double-clic sur `lancer.bat` avant de lancer LoL. Le coach attend une partie.
2. La partie démarre : « Coach prêt. Jinx contre Caitlyn et Leona. Leur jungler : Lee Sin. »
3. Pendant la lane, il parle peu et au bon moment : « 1300 gold. Crash la vague canon et back. »,
   « Drake dans une minute. Pousse ta wave, puis ward la rivière. »,
   « Leur jungler vient d'apparaître en top. Tu as vingt secondes pour jouer agressif. »
4. Une petite fenêtre au premier plan rappelle le dernier conseil et les prochains timers.
5. Fin de partie : un rapport HTML s'ouvre avec la timeline des conseils, les morts et leur
   contexte, le farm, l'or dormant et la vision.

## Cadre Riot (décision du 2026-10-04)

- Le coach lit **uniquement** la Live Client Data API (`https://127.0.0.1:2999`), prévue par Riot
  pour les outils tiers. Aucune lecture mémoire, aucune action dans le jeu.
- La politique de Riot classe les conseils temps réel du type « go here now » parmi les usages non
  approuvés pour les apps tierces. Firas a choisi, en connaissance de cause, le niveau `coach`
  en direct partout. Le risque est le sien.
- Le réglage `niveau` dans `config.toml` permet de redescendre en une ligne :
  `coach` (faits + conseil), `faits` (constats seuls, niveau Porofessor), `silencieux`
  (enregistrement + débrief).

## MVP

- [x] Lecture de la Live Client Data API, attente automatique d'une partie
- [x] Simulateur de partie pour tester sans lancer LoL
- [x] Moteur de règles ADC : objectifs, recall/or, vague canon, vision, jungler, niveaux,
      avantage numérique, farm, écart d'items, tours
- [x] Anti-spam : priorités, une seule annonce par situation, péremption des conseils en retard
- [x] Voix française (synthèse Windows hors ligne)
- [x] Mini fenêtre au premier plan (dernier conseil + timers)
- [x] Enregistrement de la partie + débrief HTML
- [x] Tests automatiques sur une partie simulée

## Plus tard

- Profil support, puis les autres rôles (un fichier de règles par rôle)
- Prix et recettes d'items via Data Dragon : « Lame d'infini achetable »
- Type de partie via l'API du client (classée, perso, bots) et niveau différent par file
- Lecture de la minimap par capture d'écran : position du jungler, état des waves. C'est la
  brique la plus proche de ce que Riot appelle « altering your field of intelligence » : à
  rediscuter avant de la brancher en partie classée.
- Voix neuronale (plus naturelle), débrief commenté par un LLM
- Matchups : conseils spécifiques par champion

## Non

- Lire la mémoire du jeu, injecter des entrées, automatiser une action
- Distribuer l'outil

## Stack

| Choix | Pourquoi | Si ça coince |
|---|---|---|
| Python 3.12, bibliothèque standard uniquement | Déjà installé, même stack que JARVIS, rien à installer | — |
| `urllib` + `ssl` | L'API locale est en HTTPS auto-signé sur 127.0.0.1 | `requests` |
| Voix : `System.Speech` via un PowerShell persistant | Voix FR déjà sur la machine, hors ligne, instantané | `edge-tts` (neuronal, en ligne) |
| Fenêtre : `tkinter` | Fourni avec Python, suffit pour un bandeau au premier plan | PySide6 |
| Débrief : HTML généré, un seul fichier | S'ouvre partout, pas de serveur | — |
| Tests : `unittest` | Fourni avec Python | pytest |

## Risques / inconnues

1. **Ce que l'API donne vraiment en partie réelle.** Le CS des ennemis pourrait être arrondi, le
   champ `price` des items et les noms de tours sont à confirmer. À vérifier dès la première
   partie en Practice Tool.
2. **Pas de positions ni d'état de wave dans l'API.** Les conseils de wave reposent sur l'horloge
   (vagues canon) et l'or, pas sur ce qui est à l'écran.
3. **Timings 2026.** Les spawns sont vérifiés sur le wiki officiel ; les fenêtres de gank sont
   des estimations (camps avancés à 0:55), à calibrer.
4. **Fenêtre au premier plan** : ne s'affiche au-dessus du jeu qu'en mode fenêtré sans bordure.

## Plan

### Structure

```
lol-coach/
  SPEC.md  README.md  lancer.bat
  config.toml            réglages (niveau, voix, fenêtre, seuils)
  donnees/saison.toml    timers de la saison (une seule source de vérité)
  docs/CONNAISSANCES.md  ce que le coach sait, avec les sources
  lolcoach/
    client.py            lit l'API du jeu                      (réseau)
    etat.py              JSON brut -> Etat typé                (pur)
    suivi.py             mémoire entre deux lectures           (pur)
    regles.py            Etat + Suivi -> Conseils              (pur)
    moteur.py            enchaîne tout, anti-spam              (pur)
    voix.py              parle                                 (effet de bord)
    fenetre.py           affiche                               (effet de bord)
    enregistreur.py      écrit la partie sur disque            (fichiers)
    debrief.py           partie enregistrée -> rapport HTML    (fichiers)
    simulateur.py        faux serveur de jeu pour les tests    (réseau)
    __main__.py          python -m lolcoach
  tests/
  parties/  rapports/    (ignorés par git)
```

Types centraux : `Etat` (une photo de la partie), `Suivi` (ce qu'on a retenu des photos
précédentes : timers, derniers achats, dernière apparition du jungler), `Conseil` (clé,
priorité, fait, action).

### Jalons

- [x] **1. Squelette** : simulateur -> client -> état -> une règle -> console. Dépôt créé.
- [x] **2. Règles ADC** complètes, anti-spam, tests sur partie simulée.
- [x] **3. Voix + fenêtre.**
- [x] **4. Enregistrement + débrief HTML.**
- [ ] **5. Vraie partie** en Practice Tool : vérifier les inconnues de l'API, calibrer les seuils.
