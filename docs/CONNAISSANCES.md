# Ce que le coach sait

Base de connaissances du coach, profil ADC. Chaque bloc donne le principe, puis la règle que le
code applique (`regles.py`). Les chiffres vivent dans `donnees/saison.toml` et `config.toml`.

Fiabilité : **[vérifié]** = lu sur le wiki officiel le 2026-10-04 ; **[consensus]** = répété par
plusieurs guides de coachs ; **[estimé]** = déduit, à calibrer en vraie partie.

## 1. Horloge de la saison 2026

| Événement | Temps | Fiabilité |
|---|---|---|
| Première vague de sbires | 0:30, puis toutes les 30 s | vérifié |
| Vagues toutes les 25 s | à partir de 14:00 | vérifié |
| Vagues toutes les 20 s | à partir de 30:00 | vérifié |
| Camps de jungle | 0:55 (avant 2026 : 1:30) | vérifié |
| Crabes | 2:55, respawn 2:30 | vérifié |
| Premier drake | 5:00, respawn 5:00 après la mort | vérifié |
| Âme | 4e drake d'une équipe, puis Elder toutes les 6:00 | vérifié |
| Grubs | 8:00, une seule fois, disparaissent à 14:45 | vérifié |
| Herald | 15:00, disparaît à 19:45 | vérifié |
| Baron | 20:00, respawn 6:00 | vérifié |
| Atakhan | supprimé en 2026 | vérifié |
| Plaques de tour | permanentes en 2026 (plus de chute à 14:00) | vérifié |

Attention : beaucoup de guides en ligne traînent encore les anciens chiffres (camps à 1:30,
crabe à 3:30, Herald à 14:00, grubs à 6:00). Le wiki fait foi.

Nouveautés 2026 utiles à l'ADC : quête de rôle (or bonus, 7e emplacement pour les bottes),
Faelights (emplacements de ward qui voient plus loin), homeguard jusqu'à la tour extérieure.

## 2. Recall

**Principe [consensus].** On ne back pas quand on a envie, on back quand la wave le permet : on
pousse la vague sous la tour adverse, puis on recall pendant que leur tour la nettoie. On revient
quand la vague suivante arrive, sans rien perdre. La vague canon est la meilleure ancre : elle
pousse fort et met longtemps à mourir sous la tour.

- Back avec de quoi acheter quelque chose qui compte : environ 1300 gold pour un gros composant.
- Ne jamais recall avec une vague qui pousse vers sa propre tour : on perd la vague entière.
- Dormir sur 1200 à 2000 gold non dépensés, c'est jouer avec un item de moins.
- PV bas : pousser d'abord si c'est possible, sinon partir. Une mort coûte plus qu'une vague.
- Avant un objectif : reset 75 à 90 s avant, pour arriver avec ses items et ses PV.

**Règles du coach.**
- Or ≥ `or_recall` depuis le dernier achat → « Crash la wave et back. »
- Or ≥ seuil et vague canon dans moins de 20 s → « C'est cette vague qu'on crash avant de back. »
- Or ≥ `or_dormant` → rappel plus ferme.
- PV sous `pv_bas` → back ; sous `pv_critique` → back immédiat.
- Objectif dans 75 à 90 s et or ≥ `or_reset_objectif` → « Reset maintenant. »
- Mort avec beaucoup d'or en poche → noté pour le débrief.

## 3. Gestion de wave

**Principe [consensus].**
- **Freeze** : garder la vague juste devant sa tour, avec 3 ou 4 sbires ennemis de plus. À faire
  quand on est en avance, quand le support roam, quand leur jungler est côté bot.
- **Slow push** : ne tuer que les last hits pour empiler 2 ou 3 vagues, puis crash. À faire avant
  un back, un roam, un dive ou un objectif.
- **Fast push** : tout tuer vite. À faire quand un ennemi est mort, ou 30 à 45 s avant un drake.
- **Crash puis reset** : la base du tempo en lane.
- Pousser sans vision et sans savoir où est leur jungler, c'est le mauvais moment.

**Limite.** L'API ne donne pas l'état de la vague. Le coach raisonne sur l'horloge (vagues canon),
l'or, les morts et les objectifs. Lire la vague à l'écran est prévu plus tard.

## 4. Objectifs

**Principe [consensus].** Un objectif se prépare une minute avant : vague poussée pour avoir la
priorité, vision posée, wards adverses nettoyées, équipe groupée. Arriver en retard ou seul dans
la rivière est la pire option.

- Drake (côté bot) : c'est l'objectif de la botlane. Push 30 à 45 s avant, puis décale.
- Grubs et Herald (côté top) : ton jungler est en haut, donc bot joue safe. Si l'ennemi fait
  l'objectif d'en haut, on prend quelque chose en bas, et inversement.
- Point d'âme (3 drakes) : le drake suivant passe avant tout.
- Baron : à partir de 20:00, ne plus être seul en side sans vision.
- Ennemis morts = objectif. Trois morts ou plus : Baron, drake ou tour, pas un retour base.

## 5. Jungler adverse

**Principe [consensus].**
- Côté de départ : la botlane qui arrive en retard a leash, donc le jungler a commencé bot.
- 4 CS = 1 camp. 12 CS = 3 camps (niveau 3, gank possible). 24 CS = full clear.
- Un full clear se termine au spawn des crabes : le jungler sort alors par la rivière.
- Si on ne sait pas où il est, on fait comme s'il venait pour nous.
- Ward avant de dépasser la moitié de la lane, pas après.
- Jungler vu à l'opposé = fenêtre pour jouer agressif ou prendre un objectif.
- Jungler niveau 6 = gank avec ulti, dive possible.

**Fenêtres 2026 [estimé].** Les camps apparaissent 35 s plus tôt qu'avant : premier gank
niveau 3 vers 2:10, sortie de full clear vers 2:55. Ensuite : retour de base avec item vers
7:00 à 9:00.

**Règles du coach.**
- 2:05 → rappel de la fenêtre de gank niveau 3.
- 2:55 → crabes, le jungler sort de son clear.
- Indice de position à chaque kill, objectif ou tour où il participe :
  - en top (kill, Herald, Baron, tour top) → « Tu es safe 30 secondes » ;
  - 30 secondes plus tard, sans nouvel indice → « Ta fenêtre est finie. Avancé : recule. Sous
    tour : c'est le moment de back. » ;
  - mid → « Il peut descendre vite » ;
  - drake pris par lui → il est côté bot, gank probable.
- Jungler adverse mort → fenêtre pour drake ou vision ; à sa réapparition, 25 secondes avant
  qu'il puisse être bot.
- Jungler adverse niveau 6 → alerte.
- Aucune nouvelle depuis `jungler_inconnu` secondes en phase de lane → prudence.

**Limite.** Le coach ne regarde pas la minimap : il ne voit pas le jungler apparaître ni clear
ses camps. Il sait où il s'est montré par un kill, un objectif ou une tour, son niveau, son
stuff, s'il est mort, et les fenêtres de l'horloge. Entre deux indices, il raisonne sur le temps
de trajet.

## 6. Niveaux

- Niveau 2 en duo : première vague + 3 mêlées de la deuxième (9 sbires) **[consensus, à
  vérifier : une source dit 7]**. Celui qui l'a en premier avance et trade tout de suite.
- Si l'ennemi l'a en premier : reculer, lâcher un ou deux CS.
- Niveau 6 : si ton ulti est meilleur, jouer pour cette fenêtre ; sinon reculer quand ils passent 6.

## 7. Trades et avantage numérique

- Trader avec au moins deux avantages parmi : cooldowns, sbires, position.
- Jamais dans leur vague, jamais quand le support adverse a son contrôle disponible.
- Vague plus grosse chez toi : trade long possible. Plus grosse chez eux : trade court ou rien.
- Un ennemi mort en bot : pousser, plaques, puis back. Pas de dive sans vague.
- Support mort ou parti : farm sous tour, pas de push.

## 8. Vision

- Début de partie : rivière et tribush pour repérer leur jungler.
- Contre un support à grab ou engage : ward ou pink dans le buisson de lane.
- Une pink à chaque back, posée là où ton équipe contrôle.
- Vision d'objectif 60 s avant le spawn ; nettoyer les wards adverses pendant le setup.
- Fin de partie : ne jamais entrer dans un buisson non éclairé.

## 9. Farm et pics de puissance

- Objectif : 8 CS par minute et plus ; le coach alerte sous `cs_par_minute`.
- 10 CS valent à peu près un kill en or.
- Premier item vers 10 à 13 min, deuxième vers 18 à 22 min : c'est à deux items que l'ADC
  devient la menace principale.
- En retard : farm sous tour, rester groupé, viser les deux items sans mourir.

## 10. Milieu de partie

- Après la première tour bot (dans un sens ou dans l'autre), l'ADC va mid : c'est la lane la
  plus courte, donc la plus sûre.
- En side seulement avec de la vision ou des alliés à côté.
- Rôle : prendre les vagues mid, décaler aux objectifs des deux côtés.

## Sources

Politique et API :
- [Riot Developer Portal, League of Legends](https://developer.riotgames.com/docs/lol)
- [Riot Support, Third Party Applications](https://support.riotgames.com/en-us/riot/events/third-party-applications)
- [Riot, Vanguard FAQ for Third Party Applications](https://www.riotgames.com/en/DevRel/vanguard-faq)

Saison 2026 :
- [Riot, /dev: 2026 Season One Gameplay Preview](https://www.leagueoflegends.com/en-us/news/dev/dev-2026-season-one-gameplay-preview/)
- Wiki officiel : [Voidgrubs](https://wiki.leagueoflegends.com/en-us/Void_Grub),
  [Rift Herald](https://wiki.leagueoflegends.com/en-us/Rift_Herald),
  [Rift Scuttler](https://wiki.leagueoflegends.com/en-us/Rift_Scuttler),
  [Blue Sentinel](https://wiki.leagueoflegends.com/en-us/Blue_Sentinel),
  [Minion](https://wiki.leagueoflegends.com/en-us/Minion_(League_of_Legends)),
  [Dragon pit](https://wiki.leagueoflegends.com/en-us/Dragon_pit)

Guides :
- [dodge.gg, Bot Lane (ADC) Guide 2026](https://www.dodge.gg/en-US/lol/news/bot-lane-adc-guide-2026)
- [dodge.gg, Support Role Guide 2026](https://www.dodge.gg/en-US/lol/news/support-role-guide-2026)
- [dodge.gg, Jungle Guide 2026](https://www.dodge.gg/en-US/lol/news/jungle-guide-2026)
- [boostroom, Laning phase: trading, level spikes, recall timings](https://boostroom.com/blog/laning-phase-guide-trading-patterns-level-spikes-and-recall-timings)
- [metabot.gg, When to recall](https://metabot.gg/en/league/guides/when-to-recall-back-timing-economy)
- [Mobalytics, Jungler tracking](https://mobalytics.gg/blog/jungler-tracking/)
- [WeCoach, Challenger vision control guide](https://wecoach.gg/blog/article/ward-like-a-pro-challenger-league-of-legends-vision-control-ward-guide)
- [lol-brain, Objective timers](https://www.lol-brain.com/blog/objective-timers-guide)

Limite de cette base : ce sont des guides écrits. Le contenu vidéo des coachs Challenger n'a pas
pu être lu directement ; il est à intégrer au fil des parties.

## 11. Matchup et composition

**Principe [consensus].** La lane ne se joue pas pareil selon ce qu'il y a en face.
- Support à accroche (Blitzcrank, Thresh, Nautilus, Pyke) : rester derrière ses sbires.
- Support d'engage (Leona, Alistar, Rell) : garder la vague de son côté ; ses niveaux 2, 3 et 6
  décident de la lane.
- Enchanteur (Lulu, Nami, Soraka) : ils gagnent les trades longs ; trader court quand le sort
  clé est parti.
- Mage ou artillerie (Xerath, Zyra, Brand) : esquiver d'abord, farmer ensuite.
- Écart de portée entre les deux ADC : celui qui a la portée harcèle à chaque last hit ; l'autre
  joue ses sorts et ses niveaux.
- ADC qui scale (Jinx, Kog'Maw, Vayne, Kai'Sa) : la lane se joue pour le farm. ADC dominant
  (Draven, Caitlyn, Lucian) : sortir à égalité, c'est avoir perdu.

**Règles du coach.** À 0:08, deux phrases de plan de lane tirées du support adverse, de l'écart
de portée, de l'archétype de ton champion et de ton support. Au niveau 6 d'un support ou d'un
jungler dont l'ulti engage de loin : garder le Flash pour l'esquiver.

**D'où ça vient.** Classes, portée et type de dégâts : données ouvertes Meraki Analytics. Listes
fines (accroches, soigneurs, ultis d'engage) : `donnees/champions_notes.toml`, tenues à la main.

## 12. Build et objets d'adaptation

**Principe [consensus].** Le premier objet est celui du champion : un carry sans dégâts ne sert à
rien, même vivant. Ensuite on répond à la partie, et d'autant plus tôt que le besoin est grave.
- Un champion qui te sort du combat d'un sort (Malzahar, Warwick, Mordekaiser, Zed) : Ceinture de
  mercure, puis Cimeterre mercuriel sur un tireur.
- Des soigneurs : Marque du bourreau tôt, Rappel mortel ensuite. Rappel mortel et Salutations de
  Dominik ne se cumulent pas : face aux soins et à l'armure, Rappel mortel fait les deux.
- Un ennemi qui a acheté de l'armure, ou deux tanks : Salutations de Dominik (Bâton du vide contre
  la résistance magique sur un build magique).
- Un assassin ou un plongeur nourri : Arc-bouclier immortel sur un build critique, Ange gardien en
  on-hit, Sablier de Zhonya sur Kai'Sa. Contre du burst magique en on-hit : Au bout du rouleau.
- Trois contrôles ou plus : Sandales de Mercure. Quatre physiques dont un assassin : Coques en acier.
- Les bottes se finissent après le premier objet. La quête de rôle les range ensuite dans un
  septième emplacement : le build compte six objets en plus des bottes.
- Lame d'infini jamais en premier : son passif demande 40 % de critique.
- Le meilleur recall est celui qui termine un objet : c'est un pic de puissance.

**Règles du coach** (`lolcoach/achats.py`). Chaque besoin reçoit un score recalculé à chaque
lecture, d'après ce que la partie montre et pas seulement d'après la sélection des champions :
- suppression : 3, plus le score de celui qui la lance (jusqu'à 4,5) ;
- survie : 3 dès qu'un plongeur ou un burst a deux kills d'avance sur ses morts ou 800 gold de
  puissance d'avance sur toi, plus son score, plus 0,5 si tu portes une prime ou si aucun
  enchanteur ni gardien ne te protège ;
- anti-soin : 1 + le nombre de soigneurs, plus 0,5 par soigneur nourri (un porteur de vol de vie
  nourri compte comme soigneur) ;
- pénétration : 2,5 pour deux tanks, 3,5 et plus dès qu'un ennemi a acheté 90 d'armure (ou 60 de
  résistance magique).

Un besoin passe devant le build type à partir de 4 avec un objet fini, de 3 avec deux, de 2
ensuite. Tant que le build type n'est pas fini, un seul objet de situation par objet de dégâts.

Quand le coach parle d'objets :
- 0:25 le build type, 0:45 la lecture de la compo et ce qu'elle fera acheter ;
- à chaque mort, ce qu'il faut prendre avec l'or en poche (« finis X », « tel composant, en route
  vers X », « garde ton or, il manque N ») ;
- au conseil de back, la même phrase ; « X gold : objet finissable » quand l'or termine l'objet ;
- huit secondes après un achat, le prochain objet visé ;
- en cours de partie, « Change de plan : X avant Y » avec la raison, dès qu'un besoin passe devant
  (un Zed qui prend trois kills, un tank qui finit sa Cotte épineuse).

**Limite.** Les chemins d'items et les objets de situation sont des repères par famille (crit,
lanceur, on-hit, létalité, Kai'Sa), écrits à la main à partir de guides : ce ne sont pas les
statistiques du patch. Les seuils sont un réglage, pas une vérité. Le chemin de Kai'Sa (Tueur de
krakens, Lame enragée de Guinsoo, Terminus) suit ce que Firas joue en classée. Les objets des
ennemis ne sont connus que quand ils ont été vus.

## 13. Macro avancée

**Principe [consensus].**
- Un kill n'est qu'un moyen : il doit donner une tour ou un objectif dans les trente secondes.
- Objectif dans moins de deux minutes après un kill : on y va, on ne back pas.
- Être sur place une minute avant un objectif, avec PV et objets.
- Baron seulement en supériorité numérique, avec la vision, et de quoi le finir.
- Baron pris : back, achat, puis siège avec les sbires renforcés. Baron perdu : nettoyer les
  vagues sous tour, pas de combat dans leurs sbires, tenir trois minutes.
- De 14 à 20 minutes, l'ADC est au plus fragile : assassins en ligne, build incomplet. Rester
  avec support et jungler.
- En combat : derrière la frontline, la cible la plus proche d'abord.
- Devant : convertir vite. Derrière : ne contester que sous vision et attendre l'erreur.
- Porter une prime, c'est jouer derrière sa frontline ; une prime adverse se prend à plusieurs.
- Niveau 9 : trinket bleu.

**Règles du coach.** État de la partie toutes les cinq minutes (kills, tours, drakes), écart de
farm avec l'ADC adverse, infériorité numérique, jungler allié mort au moment du drake, plan de
combat deux minutes avant le Baron, consignes après Baron, âme et Elder.

## 14. Ce que la vraie partie a appris sur l'API (2026-10-04)

- `price` est le coût de combinaison d'un objet, pas son prix : Tueur de krakens y vaut 325.
- Les sbires sont arrondis à la dizaine inférieure, pour tous les joueurs. Compter les camps du
  jungler adverse par son CS est donc impossible.
- Les tours s'appellent `Turret_TChaos_L0_P3_...` : L0 bot, L1 mid, L2 top ; P3 extérieure.
- Les événements nomment un humain par son `riotIdGameName`, un bot par son `summonerName`.
- `HordeKill` signale un grub tué. Il n'existe pas d'événement pour les pings ni pour le chat.
- Dans l'outil d'entraînement, l'heure des événements avait 37 secondes de retard sur l'horloge.

Sources ajoutées :
- [buildzcrank, LoL Macro Guide 2026](https://buildzcrank.com/en/blog/macro-guide-league-of-legends-2026/)
- [buildzcrank, LoL Itemization Guide 2026](https://buildzcrank.com/en/blog/lol-itemization-guide-2026/)
- [goboost, How to close out games](https://goboost.gg/blog/lol-macro-guide-how-to-close-out-games-and-break-the-20-minute-aram-2026/)
- [dodge.gg, Attack speed and crit items 2026](https://www.dodge.gg/en-US/lol/news/attack-speed-crit-items-2026)
- [loltheory, Wave management](https://blog.loltheory.gg/wave-management-league-of-legends/)
- [Meraki Analytics, lolstaticdata](https://github.com/meraki-analytics/lolstaticdata)
- [Riot Data Dragon](https://ddragon.leagueoflegends.com/api/versions.json)

## 15. Lire l'adversaire

**Principe [consensus].** Une lane se gagne en punissant ce que l'adversaire vient d'utiliser.
- Le sort avec lequel un support attrape ou immobilise a un long temps de recharge au niveau 1
  (Grappin de Blitzcrank 20 s, Peine capitale de Thresh 19 s, Abordage de Nautilus 14 s, Lame du
  zénith de Leona 12 s). Raté ou utilisé, il ouvre une fenêtre pour trader.
- La rune principale dit comment l'adversaire veut se battre : Déluge de lames gagne le trade
  court, Tempo mortel le combat long, Après-coup rend un engage intuable pendant trois secondes,
  Gardien absorbe le premier all-in.
- Ignite en face : les all-in tuent dès le niveau 2. Exhaust : ton all-in sera coupé, il faut le
  faire sortir d'abord.
- Un objet défensif acheté en face change la cible : Ange gardien et Sablier de Zhonya se
  gardent pour la fin, un bouclier anti-sort se fait sauter avec un petit sort, Cœur gelé et
  Présage de Randuin réduisent ce que fait un ADC à l'auto.

**Règles du coach.** À 1:00, le sort clé du support adverse avec sa recharge, puis la rune ou le
sort d'invocateur le plus dangereux de leur botlane. Pendant la partie : une annonce quand un
ennemi achète un objet défensif de la liste ; « deux niveaux d'avance » pour leur ADC.

**D'où ça vient.** Noms et temps de recharge des sorts, noms des runes : Data Dragon, patch en
cours. Le choix du sort clé de chaque support, et ce que chaque rune et chaque objet change :
`donnees/champions_notes.toml`, tenu à la main.

## 16. Tournants de partie

- Ace pour vous : la fin si leurs réapparitions dépassent 35 secondes, sinon Baron, sinon tours
  et drake. Ace pour eux : défendre à cinq sous les tours.
- Inhibiteur détruit : les super-sbires poussent seuls, on joue l'objectif du côté opposé.
  Inhibiteur perdu : quelqu'un nettoie les super-sbires, pas d'objectif à quatre.
- Leur inhibiteur revient dans 30 secondes : dernière fenêtre pour forcer.
- À 15 minutes : le plan de combat de ton équipe d'après sa composition (engage, protection,
  poke, plongée).
- Tours 2026 **[vérifié]** : cinq plaques à 120 gold, 300 gold pour la première tour, et une
  charge cristalline qui donne un bonus de dégâts à la première attaque d'un champion.

Sources ajoutées :
- Wiki officiel : [Turret](https://wiki.leagueoflegends.com/en-us/Turret),
  [Experience](https://wiki.leagueoflegends.com/en-us/Experience_(champion))
- [Riot, notes de patch 14.21 (primes)](https://www.leagueoflegends.com/en-us/news/game-updates/patch-14-21-notes/)

## 17. Rapport de force et arbitrage

**Principe.** Un conseil n'a de sens que rapporté à l'état du joueur. On ne dit pas « recule » à
un carry qui a 2000 gold d'avance, ni « force le trade » à celui qui en a 2000 de retard. Et un
coach ne dit jamais deux choses contraires dans la même minute.

**Rapport de force** (`rapport.py`). La puissance d'un joueur est l'or de ses objets plus 300 par
niveau. Pour un ennemi, dont on ne voit les objets que quand il est visible, on ne descend pas
sous ce que son score laisse supposer. De là :
- l'avance sur chaque ennemi, et sur le plus fort des deux adversaires de lane ;
- la forme du joueur : « domine » à 1500 gold au-dessus de la moyenne adverse, « retard » à
  1500 en dessous.

Devant, les conseils de prudence se taisent ou changent de sens : support mort, niveau de retard,
jungler pas vu, grubs. Les menaces sont lues contre ta propre force : un ennemi nourri que tu
domines devient une prime à prendre.

**Arbitrage** (`moteur.py`). Chaque conseil porte une intention. En cas de conflit, la plus
importante passe et l'autre attend :

| Rang | Intention | Exemples |
|---|---|---|
| 1 | danger | PV critiques, infériorité numérique, Baron ennemi |
| 2 | objectif | trois ennemis morts, botlane morte, jungler mort et drake libre |
| 3 | agressif | avance d'objets, niveau avant eux, pic d'objet |
| 4 | tempo | drake ou Baron dans une minute |
| 5 | back | or suffisant, objet finissable, reset avant objectif |
| 6 | prudent | niveau de retard, jungler pas vu, ennemi nourri |

Sont contraires : objectif et back, tempo et back, objectif et prudent, agressif et prudent,
danger et agressif, danger et objectif. Une même intention n'est pas redite avant 45 secondes pour
le back, 40 pour la prudence, 30 pour l'agressif. Un conseil écarté revient s'il est encore vrai
après le conflit.

Trois garde-fous d'état, ajoutés après la partie du 5 octobre 2026 (« prends une tour » dit à
33 % de PV avec un objet finissable) :
- un joueur à 35 % de PV ou moins depuis plusieurs lectures ne reçoit aucun conseil d'intention
  objectif ou agressif : sa seule décision est de rentrer ;
- un ordre urgent se décide sur l'état du moment, pas sur ce qui a été dit trente secondes plus
  tôt ;
- quand la partie retourne une consigne que le joueur vient d'entendre, le coach le dit : « Le
  back attendra. », « Changement de plan. », « Stop. ».

Et l'état du joueur filtre les conseils qui poussent au combat (`rapport.peut_presser`) : pas en
retard d'un demi-objet sur son adversaire de lane, pas après deux morts avant dix minutes, pas à
trois morts de plus que de kills, pas face à un adversaire de lane nourri qu'il ne domine pas.
Un drake ne se propose qu'avec le jungler allié en vie et sans infériorité numérique.

## 18. Après un combat gagné : back, objectif ou tour

**Principe [consensus].** Trois ennemis morts ouvrent une fenêtre qui dure jusqu'au premier
retour. Ce qu'on en fait dépend de soi autant que de la carte.
- Bas en PV, on ne prend rien : mais c'est le back le plus sûr de la partie, et il se prend tout
  de suite. « Une plaque de plus » ne vaut pas une mort avec une prime sur la tête.
- En forme : un objectif neutre disponible passe avant une tour (Baron à quatre vivants avec le
  jungler, drake avec le jungler ou à trois).
- Sinon la tour, sur la lane où l'on se trouve : bot pendant la phase de lane, mid ensuite. Un
  inhibiteur à découvert passe avant une tour.
- De l'or à dépenser et moins de quinze secondes avant leur retour : pas le temps pour une tour,
  on rentre acheter.
- Les cinq morts pour vingt secondes après 15 minutes : on finit, quels que soient les PV.

**Règle du coach** (`carte.apres_combat`). Une seule consigne, qui nomme la structure (« La tour
mid intérieure, avec la vague. ») et dit quoi faire de l'or (« Back juste après : tu as 1500 gold
à dépenser. », ou « À la boutique : finis Percepteur. »). Rien n'est dit si les morts reviennent
dans moins de huit secondes.

## 19. Où être sur la carte en milieu de partie

**Principe [consensus].**
- Dès qu'une tour extérieure bot tombe, d'un côté ou de l'autre, l'ADC va mid : c'est la lane la
  plus courte, donc celle où l'on rejoint sa tour le plus vite. Les sides sont pour les joueurs
  qui ont un Téléport ou un duel.
- Mid, on ne pousse qu'avec son support à côté ou le jungler adverse vu ailleurs. Sinon on laisse
  la vague venir.
- Une vague de side se prend quand elle arrive à sa tour, puis on revient mid dans les quinze
  secondes. Jamais seul en side à l'opposé de son équipe.
- Chaque tour perdue recule la limite : devant la tour intérieure une fois l'extérieure tombée,
  et plus de side seul quand deux tours sont tombées sur une lane.
- On ne suit pas tous les combats : on se demande si on sera revenu pour la vague suivante.
- Un allié farme déjà la vague : on ne la partage pas. On prend les camps de sa jungle du côté
  du prochain objectif, puis la vague suivante. Si le midlaner ne laisse pas la lane, on tient
  la lane libre sous sa tour.
- En retard avec la tour extérieure perdue : geler la vague devant la tour intérieure et ne
  prendre que ce qui arrive.
- Une minute avant un objectif, on passe par mid et on arrive avec son équipe, jamais le premier
  dans la rivière.

**Règle du coach** (`carte.directions`). Le coach ne voit pas les positions. Il sait quelles tours
sont debout des deux côtés, qui est mort et pour combien de temps, quel objectif arrive et de quel
côté, et l'état du joueur. Il en tire un endroit, puis des solutions de repli :
- en supériorité de deux joueurs : la décision de la section 18 ;
- bas en PV : le back d'abord ;
- en infériorité : sous la tour mid, sans combat avant le retour des alliés ;
- objectif dans les 75 secondes, ou disponible et jouable : y aller par mid ;
- sinon mid, à la profondeur que les tours permettent ; puis la side du prochain objectif ; puis
  la jungle si un allié tient déjà la vague.

Il parle de placement à chaque tour qui change la donne (tour bot, tour mid alliée), au retour
d'une mort quand un objectif ou le nombre décident de l'endroit, et à la demande : une touche
(Ctrl+F6) donne la meilleure réponse, un nouvel appui dans les 25 secondes donne la suivante.
C'est la réponse au cas que le coach ne peut pas voir : la vague déjà prise par un allié, ou la
lane tenue par un ennemi plus fort.

**Limite.** Ces règles viennent de guides écrits, pas de l'analyse de replays ou de vocaux de
joueurs Challenger : le coach ne sait ni regarder une vidéo ni écouter un stream. Sans les
positions, il donne un plan par l'état de la partie ; ce qui se voit à l'écran reste au joueur.

Sources ajoutées :
- [dodge.gg, Bot Lane (ADC) Guide 2026](https://www.dodge.gg/en-US/lol/news/bot-lane-adc-guide-2026)
- [games.gg, League of Legends ADC Guide](https://games.gg/league-of-legends/guides/league-of-legends-adc-guide/)
- [Mobalytics, How to play behind as ADC](https://mobalytics.gg/lol/guides/how-to-play-behind-adc)
- [r/summonerschool, What should an ADC do (mid game)](https://lr.us.psf.lt/r/summonerschool/comments/1duknnt/what_should_an_adc_do)
- [GuildOrder, Role and lane theory](https://guildorder.com/games/league/guides/role-and-lane-theory)

Trois ennemis morts : ni back ni alerte de PV, on prend un objectif ; tous morts pour vingt
secondes ou plus après 15 minutes, on finit la partie.
