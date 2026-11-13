# Scénarios et trajets

## Qu'est-ce qu'un scénario ?

Un scénario est **un lieu et une heure de départ** de nuit, choisis pour raconter une situation : sortie
de concert, de bar, d'hôpital après une garde, arrivée à l'aéroport…

| Scénario | Départ |
|---|---|
| AccorHotel-Arena-0h, La-Defense-0h | minuit |
| Mogador-1h, Stade-de-France-1h | 1 h |
| Pigalle-2h | 2 h |
| Descartes-3h, Roissy-3h | 3 h |
| Metropolis-4h | 4 h |
| Beclere-5h, CHU-Avicenne-5h, Noct-5h | 5 h |

Tous partent dans la nuit du samedi 7 au dimanche 8 novembre 2026, d'après les horaires de transport
disponibles.

## Destinations

Chaque scénario calcule un trajet vers **la mairie de chaque commune d'Île-de-France**, soit environ
1 270 destinations. Paris est découpée en ses 20 arrondissements, chacun avec sa mairie.

La **population** de chaque commune provient de `geo.api.gouv.fr`. Elle donne la taille des bulles
d'arrivée : une arrivée dans une commune peuplée représente potentiellement plus de personnes concernées.

!!! note "Population simulée"
    En mode démonstration (`?source=mock`), les données ne contiennent pas de population. Elle est alors
    simulée de façon déterministe (500 à 50 000 habitants) et signalée « (simulée) » dans l'infobulle.

## Calcul des itinéraires

Le calcul est réalisé par un pipeline dédié (`services/routing`, développé par un expert métier de
l'équipe) :

- **Réseau de transport** : horaires théoriques GTFS d'Île-de-France Mobilités.
- **Réseau piéton** : voirie OpenStreetMap.
- **Algorithme** : recherche du trajet arrivant le plus tôt, par balayage chronologique des départs
  (Connection Scan Algorithm).
- **Marche** : 1,3 m/s, soit environ 4,7 km/h.
- **Correspondances à pied** entre arrêts : 5 minutes au plus.

Un trajet est découpé en portions : **marche d'accès**, **attente**, **transport**, **correspondance**,
**marche finale**, ou **marche directe** quand aucun transport n'est utile ou disponible.

## Trajets de plus de 2 heures

!!! warning "Trajets peu plausibles"
    Un trajet de nuit de plus de **2 heures** est affiché en **gris**, avec une bulle d'arrivée creuse, et
    son indice n'est pas évalué.

**Pourquoi ?** En pleine nuit, beaucoup de destinations ne sont atteignables qu'après de très longues
marches ou en attendant les premiers transports du matin. Le calcul les produit quand même, mais une
personne réelle aurait pris un taxi ou un VTC. Les colorer selon l'indice suggérerait un vécu qui n'a pas
de sens.

Le seuil de 2 heures est un **choix de visualisation**, pas une donnée mesurée. Sur les scénarios actuels,
la majorité des trajets le dépassent : c'est en soi un résultat, qui montre la faiblesse de l'offre
nocturne hors du cœur de l'agglomération.
