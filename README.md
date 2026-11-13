# Template ReadMe des projets - [Nom du projet]

Ce document est un exemple de README pour vos répertoire de code et pour présenter vos projets. Il vous aidera à faire vos [diapositives pour votre présentation]([https://drive.google.com/drive/folders/1F9pkX9DwDJxw5rXWIiKHeD_um1sa5BH9?usp=sharing](https://docs.google.com/presentation/d/1jPF5iI2PCAjEqkCNwgHqRqyUQyygMstc/edit?usp=sharing&ouid=104935023241444229576&rtpof=true&sd=true)). 

> [!TIP]
> En début de README, on décrit le projet, son but et son fonctionnement de manière très succinte.

## Présentation du projet

Le projet Noctambulle a été développé dans le cadre du Hackaviz Mobilités 2026 spécial dataviz, organisé par Île-de-France Mobilités du 2 au 26 novembre 2026. Pour en savoir plus, voici le [Guide des participants et participantes](https://github.com/hackathons-mobilites/hackaviz_2026/blob/main/README.md). Noctambulle est un visualisateur de trajets nocturnes mettant en avant le niveau de sérénité des voyageurs durant leur trajet à pied ou en transports collectifs.


### Le problème et la proposition de valeur 
> [!TIP]
> Ici vous pouvez répondre aux questions suivantes : 
> - A quel problème votre projet répond-t-il ?
> - Quels sont les usagers cibles ? 
La vie nocturne occupe aujourd'hui une place centrale dans la dynamique économique francilienne. On pense souvent aux activités de loisirs, mais de nombreux actifs réalisent des prises de poste en horaires décalés : travailleurs hospitaliers, opérateurs des plateformes aéroportuaires, employés des marchés internationaux, techniciens de surface, employés des dits lieux de loisirs, etc. De nombreux visiteurs se retrouvent aussi lors de grands événements comme les concerts ou les rencontres sportives.

Tous ces lieux ont un rayonnement régional et attirent clients, employés ou visiteurs de toute l'Île-de-France. Le réseau de transport nocturne, fortement développé dans la région, repose sur le réseau Noctilien, organisé en étoile autour de 5 pôles intra-muros (grandes gares et Chatelêt) entre environ minuit et 6h. Le réseau ne se limite pas à Paris, mais couvre aussi les grands pôles de petite et grande couronne, bien qu'il reste inexistant dans les zones moins denses. Cette fracture entre Paris et banlieue (ou zone dense et grande couronne) se révèle plus forte que la journée, où le réseau structuré permet une desserte de la majorité de la population francilienne. Ainsi, il n'est pas rare qu'un travailleur ou un fêtard habitant en grande couronne doive voyager près de deux heures, ou "attendre le premier métro".

Au-delà des inégalités territoriales évidentes qui se posent, les noctambules sont aussi confrontés à un phénomène humain difficilement contrôlable : le sentiment d'insécurité. Si celui-ci doit bien être distingué de l'insécurité en tant que tel, nous avons toutes et tous été confrontés à des situations peu confortables, où l'absence d'éclairage ou de toute présence humaine se révèle angoissante. Ce sentiment peut influencer le choix modal et obliger certaines personnes à délaisser les transports collectifs pour éviter attentes et trajets de rabattement à pied, et renforce ainsi encore plus les inégalités sur le territoire. Le sentiment d'insécurité peut aussi avoir lieu à bord des véhicules, où la présence de trop peu de personnes peut elle aussi se révéler anxiogène.




### La solution
> [!TIP]
> Ici vous pouvez présenter 
> - Votre solution et son fonctionnement général
> - Les données mobilisées
> - Comment elle répond au problème
Noctambulle permet de visualiser les trajets depuis un point de départ à une heure donnée vers toutes les mairies d'Île de France. En plus du plus court trajet (= le trajet faisant arriver le plus tôt à la destination), elle permet d'observer en temps réel le sentiment de sécurité pour tous les voyageurs simulés. A la fin de l'animation, une carte permet de visualiser chaque destination et l'anxiété cumulée vécue par le voyageur.
Le calculateur d'itinéraires simplifié est basé sur un CSA (Connection Scan Algorithm) pour les trajets en transports collectifs et un algorithme de Dijkstra pour les trajets piétons.
Les différents scénarios (heure de départ x lieu de départ) sont précalculés par l'outil pour la Dataviz.
Le score de sérénité est défini sur la base de la luminosité nocturne et la densité d'équipements générant de l'activité la nuit pour les trajets à pied et sur le nombre potentiel de voyageurs visibles à bord d'un véhicule de transports collectifs.

Les données en entrée du programme sont :
    - Le fichier GTFS d'Île-de-France Mobilités
    - Le réseau routier d'OpenStreetMap
    - Le nombre de validations par jour sur le réseau de surface et le réseau ferré du 4ème trimestre 2025
    - Le profil horaire des validations sur le réseau de surface et le réseau ferré du 4ème trimestre 2025
    - Les données "amenities" d'OpenStreetMap
    - Les données de luminosité nocturne de [COMPLETER VICTORIA]

Noctambulle met en exergue les inégalités territoriales précédemment expliquées : en identifiant les secteurs où les temps de trajet sont les plus longs et où le sentiment d'insécurité est le plus fort, nous pourrons visualiser la fracture nocturne qui se présente sur le territoire, à la fois pour les actifs mais aussi pour les voyageurs de loisir.


### Les problèmes surmontés et les enjeux en matière de données
> [!TIP]
> Ici vous pouvez présenter les principaux problèmes rencontrés en les liant à vos solutions, ainsi que d'éventuelles recommendations à Ile-de-France Mobilités en matière d'ouverture de données et d'API qui auraient été utiles pour votre proposition
L'absence de données de données de validation sur certaines lignes nous ont forcé à émettre des hypothèses pour le "score" d'anxiété des différents services TC. De plus, les données de validation ne permettent d'avoir qu'une vision à l'échelle de la ligne (fréquentation) mais pas de l'interstation (charge), ce qui induit une approximation forte. Si des données de serpent de charge par tranche horaire étaient disponibles (ou matrices OD permettant de reconstituer ces serpents), par exemple issus des enquêtes TJRF sur le métro ou des enquêtes OD à bord pour les bus, le calcul du score de sérénité à bord des véhicules serait plus fiable. 

Noctambulle permet aujourd'hui de représenter le trajet depuis un point d'intérêt nocturne vers toutes les communes d'Île-de-France (avec une représentation pondérée par la population communale). Toutefois, si une matrice OD par heure, par exemple issue de l'Enquête Globale Transport (EGT), était disponible, l'outil pourrait être adapté pour prendre en entrée cette matrice, et afficher tous les trajets depuis le point d'intérêt vers les destinations effectivement rejointes à cette heure par les usagers (arborescence à partir du point de départ).


### Et la suite ? 
> [!TIP]
> Ici vous vous projetez sur comment vous auriez aimé développer votre projet si vous aviez eu plus de temps ! (Quel cas d'usage pour la suite ? Quelles ressources à mobiliser ?)
En ayant plus de temps, nous pourrions continuer à développer Noctambule en accélérant les calculs (optimisation des algorithmes CSA et Dijkstra), et en utilisant les API de PRIM. A terme, la faisabilité d'obtenir un outil avec calculs en quelques secondes permettrait à l'utilisateur de définir lui même ses scénarios et observer les résultats quasi-instantanément.

Une autre évolution serait de définir un mode supplémentaire, où l'utilisateur choisit un point et une heure d'arrivée plutôt que de départ, afin de visualiser les voyageurs se rendant sur un lieu nocturne. Ceci serait particulièrement intéressant pour les prises de poste tôt le matin (autour de 5h), par exemple dans les aéroports, au MIN de Rungis, ou dans certains hôpitaux.

Enfin, nous ne pondérons actuellement pas l'influence de la luminosité nocturne en fonction de l'heure de la journée, ce qui serait important si l'on souhaitait modéliser des trajets de fin de nuit (départ 5h par exemple) durant la saison estivale.



## Installation et utilisation
> [!TIP]
> Si vous avez le temps, vous pouvez décrire les étapes d'installation de votre projet (commandes à lancer, ...) et son fonctionnement.
Pour afficher la dataviz, il suffit de [COMPLETER FLORIAN]

Pour recalculer des scénarios, il faut les définir dans le fichier data/scenarios.json et lancer la commande :
uv run --package routing transit-accessibility-scenarios `
  --scenarios data\scenarios.json `
  --all-communes
Il est possible d'ajouter un argment --max-destinations XX pour limiter le calcul à XX communes de destinations.

Pour recalculer les scores de sérénité par arc TC, il faut lancer la commande :
uv run --package routing python services\ridership\ridership_surface.py


## La licence
> Ici, il faut décrire la ou les licences du projet. Vous pouvez utiliser la licence [MIT](https://github.com/hackathons-mobilites/hackaviz_2026/blob/main/Docs/License.md), qui est très permissive. Si on souhaite s'assurer que les dérivés du projet restent Open-Source, vous pouvez utiliser la licence [GPLv3](https://github.com/Illumina/licenses/blob/master/gpl-3.0.txt).

Le code et la documentation de ce projet sont sous licence MIT(https://github.com/hackathons-mobilites/hackaviz_2026/blob/main/Docs/License.md).