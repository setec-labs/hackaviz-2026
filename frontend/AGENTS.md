# Instructions pour les agents du frontend

## Responsabilite

Le frontend affiche la cartographie interactive, les trajets et les indicateurs produits par les services.

Le frontend ne doit pas reimplementer les calculs metier appartenant aux services.

## Interface

- Donner la priorite visuelle a la carte.
- Utiliser la palette definie dans la documentation du projet.
- Centraliser les couleurs dans le theme.
- Prevoir les etats de chargement, d'erreur et d'absence de donnees.
- Ne pas utiliser uniquement une couleur pour transmettre une information.
- Conserver une interface utilisable sur un ecran d'ordinateur portable.
- Limiter les panneaux permanents qui reduisent la surface de la carte.

## Donnees

- Utiliser les modeles partages lorsque cela est possible.
- Ne pas inventer une valeur lorsqu'une donnee est absente.
- Afficher clairement les donnees inconnues ou non disponibles.
- Distinguer donnee observee, indicateur calcule et interpretation.
- Ne pas presenter un indicateur defavorable comme une preuve objective de danger.

## Validation

Apres une modification :

- demarrer le frontend ;
- verifier l'affichage sans donnees ;
- verifier le chargement d'un trajet ;
- verifier le comportement en cas d'erreur d'un service ;
- controler les contrastes et la lisibilite.


## Palette graphique

Respecter cette palette pour l'ensemble de l'interface.

| Rôle | Couleur |
|---|---|
| Fond principal | `#061B3A` |
| Surface principale | `#0B2F5B` |
| Surface secondaire | `#164878` |
| Réseau secondaire | `#286FAE` |
| Trajet principal | `#35C5F4` |
| Sélection / survol | `#8DE5FA` |
| Texte principal | `#F3F8FC` |
| Texte secondaire | `#A9C4DD` |
| Mise en évidence | `#FFE08A` |
| Vigilance | `#FFBF47` |
| Vigilance élevée | `#FF7A45` |

### Règles d'utilisation

- Utiliser `#061B3A` comme fond principal de l'application.
- Utiliser `#0B2F5B` et `#164878` pour créer les différents niveaux de surfaces.
- Utiliser `#35C5F4` comme couleur principale pour les trajets et les interactions.
- Utiliser `#286FAE` pour les réseaux et informations cartographiques secondaires.
- Utiliser `#8DE5FA` pour les éléments sélectionnés ou survolés.
- Utiliser `#FFBF47` et `#FF7A45` pour attirer l'attention sur des indicateurs.
- Ne pas interpréter `#FF7A45` comme signifiant automatiquement "danger".
- Ne pas introduire de nouvelle couleur sans justification fonctionnelle.
- Réutiliser les variables du thème plutôt que coder directement les couleurs dans les composants.

### Variables de thème

Utiliser de préférence ces variables :