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

**Principe [consensus].** Les deux premiers objets sont ceux du champion ; à partir du troisième,
on répond à la partie.
- Un champion qui te sort du combat d'un sort (Malzahar, Warwick, Mordekaiser) : Ceinture de
  mercure avant les combats à cinq.
- Deux soigneurs ou plus : Marque du bourreau tôt, Rappel mortel ensuite.
- Deux tanks, ou un ennemi qui empile l'armure : Salutations de Dominik.
- Un assassin nourri, ou trois plongeurs : Ange gardien (Sablier de Zhonya sur un build AP).
- Trois sources de dégâts magiques : Gueule de Malmortius.
- Trois contrôles ou plus : Sandales de Mercure. Quatre physiques dont un assassin : Coques en acier.
- Lame d'infini jamais en premier : son passif demande 40 % de critique.
- Le meilleur recall est celui qui termine un objet : c'est un pic de puissance.

**Règles du coach.** À 0:25 le build type, à 0:45 la lecture de la compo et les objets à prévoir.
En partie : « X gold : objet finissable », un pic annoncé à chaque objet terminé, et le prochain
objet d'adaptation au deuxième objet.

**Limite.** Les chemins d'items sont des repères par famille d'ADC (crit, lanceur, on-hit,
létalité), écrits à la main à partir de guides : ce ne sont pas les statistiques du patch.

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
